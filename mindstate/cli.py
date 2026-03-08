import argparse
from typing import Optional

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from langchain_core.messages import AIMessage, HumanMessage

from .commands import CommandParseError, help_text, parse_slash_command
from .config import get_settings
from .db import (
    connect_db,
    execute_cypher_with_smart_columns,
    format_rows,
    init_age,
    load_and_execute_files,
    print_result,
)
from .llm import build_send_cypher_tool, create_agent_executor, create_llm
from .logging_utils import VerboseCallback, log_print, setup_logging
from .memory_models import ContextBuildInput, RecallInput, RememberInput
from .memory_service import MindStateService


def main() -> None:
    settings = get_settings()

    parser = argparse.ArgumentParser(description="MindState for AGE/PostgreSQL")
    parser.add_argument("files", nargs="*", help="Cypher files to load and execute")
    parser.add_argument("-e", "--execute", action="store_true", help="Execute files and exit (do not start REPL)")
    parser.add_argument("-t", "--tui", action="store_true", help="Launch the Textual TUI instead of the standard REPL")
    parser.add_argument("--api", action="store_true", help="Run the FastAPI service instead of the REPL")
    parser.add_argument("--api-host", default=settings.api.host, help="API host bind address")
    parser.add_argument("--api-port", type=int, default=settings.api.port, help="API port")
    parser.add_argument("-s", "--system-prompt", help="Path to a file containing a system prompt for the LLM")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output (show stack traces on errors)")
    args = parser.parse_args()

    logger = setup_logging(args.verbose)

    if args.api:
        import uvicorn

        print(f"MindState API server listening on http://{args.api_host}:{args.api_port}")
        uvicorn.run("mindstate.api:app", host=args.api_host, port=args.api_port, reload=False)
        return

    print(f"MindState for AGE/PostgreSQL - graph: {settings.graph_name}")

    # Validate LLM provider configuration early
    try:
        create_llm(settings)
    except ValueError as e:
        print(f"LLM Configuration Error: {e}")
        return

    try:
        conn, cur = connect_db(settings)
    except Exception as e:
        if args.verbose:
            raise
        from psycopg2 import OperationalError

        if isinstance(e, OperationalError):
            print(f"Database connection failed: {e}")
            print("Please ensure the PostgreSQL server is running and accessible.")
        else:
            print(f"Database error: {e}")
        return

    try:
        try:
            init_age(cur, conn, settings)
            svc = MindStateService(cur=cur, conn=conn, settings=settings)
            system_prompt = settings.default_system_prompt
            if args.system_prompt:
                try:
                    with open(args.system_prompt, "r", encoding="utf-8") as f:
                        system_prompt = f.read()
                except OSError as e:
                    print(f"Error reading system prompt file: {e}")
        except Exception as e:
            if args.verbose:
                raise
            print(f"Initialization error: {e}")
            return

        if args.tui:
            from .tui import run_tui

            # If only executing files in batch mode
            if args.execute:
                if args.files:
                    load_and_execute_files(cur, conn, args.files, settings, logger if args.verbose else None)
                print("\nExecution complete.")
                return

            run_tui(cur, conn, settings, system_prompt, verbose=args.verbose, files=args.files or None, execute_only=args.execute)
            return

        log_enabled = False
        llm_enabled = True
        workflow_mode = "shell"

        if args.files:
            load_and_execute_files(cur, conn, args.files, settings, logger if args.verbose else None)

        if args.execute:
            print("\nExecution complete.")
            return

        # Build LLM agent if possible, otherwise fall back to cypher-only mode
        agent_executor = None
        try:
            callbacks = [VerboseCallback(logger)] if args.verbose else None
            send_cypher_tool = build_send_cypher_tool(
                cur,
                conn,
                settings,
                logger if args.verbose else None,
                is_logging_enabled=lambda: log_enabled,
            )
            llm = create_llm(settings, callbacks=callbacks)
            agent_executor = create_agent_executor(llm, send_cypher_tool, system_prompt)
        except Exception as e:
            if args.verbose:
                logger.exception("LLM initialization error")
            else:
                print(f"LLM initialization error: {e}")
            print("Running in Cypher-only mode (LLM disabled)")
            llm_enabled = False

        # REPL intro
        if not args.files:
            print("Enter adds a new line. Esc+Enter executes your  Natural Language or Cypher query.")
        print("Use Ctrl+D or \\q to quit. \\h for list of commands.\n")

        session = PromptSession(history=FileHistory(settings.history_file), multiline=True)
        chat_history = []

        while True:
            try:
                text = session.prompt("mstate> ")
                stripped = text.strip()
                if not stripped:
                    continue
                if stripped == "\\q":
                    break
                if stripped.startswith("\\"):
                    try:
                        cmd = parse_slash_command(stripped)
                    except CommandParseError as e:
                        print(str(e))
                        continue
                    try:
                        if cmd.name == "quit":
                            break
                        if cmd.name == "help":
                            print(help_text())
                            continue
                        if cmd.name == "log":
                            log_enabled = cmd.args["enabled"]
                            print(f"Logging {'enabled' if log_enabled else 'disabled'}.")
                            continue
                        if cmd.name == "llm":
                            val = cmd.args["enabled"]
                            if val and agent_executor is None:
                                try:
                                    callbacks = [VerboseCallback(logger)] if args.verbose else None
                                    send_cypher_tool = build_send_cypher_tool(
                                        cur,
                                        conn,
                                        settings,
                                        logger if args.verbose else None,
                                        is_logging_enabled=lambda: log_enabled,
                                    )
                                    llm = create_llm(settings, callbacks=callbacks)
                                    agent_executor = create_agent_executor(llm, send_cypher_tool, system_prompt)
                                except Exception as e:
                                    print(f"LLM initialization error: {e}")
                                    val = False
                            llm_enabled = val
                            print(f"LLM {'enabled' if llm_enabled else 'disabled'}.")
                            continue
                        if cmd.name == "contextualize_n":
                            job = svc.contextualize_n(cmd.args["n"])
                            print(f"contextualization job queued: job_id={job.job_id or '(none)'} queued_count={job.queued_count}")
                            continue
                        if cmd.name == "contextualize_ids":
                            job = svc.contextualize_ids(cmd.args["ids"])
                            print(f"contextualization job queued: job_id={job.job_id or '(none)'} queued_count={job.queued_count}")
                            continue
                        if cmd.name == "mode":
                            workflow_mode = cmd.args["mode"]
                            print(f"Workflow mode set to {workflow_mode}.")
                            continue
                        if cmd.name == "remember":
                            result = svc.remember(
                                RememberInput(
                                    kind=cmd.args["kind"],
                                    content=cmd.args["content"],
                                    source="repl",
                                    author="user",
                                )
                            )
                            print(
                                f"Remembered {cmd.args['kind']} as memory {result['memory']['memory_id']} "
                                f"({result['chunk_count']} chunk(s))."
                            )
                            continue
                        if cmd.name == "recall":
                            results = svc.recall(
                                RecallInput(query=cmd.args["query"], limit=settings.memory.default_recall_limit)
                            )
                            if not results:
                                print("No memory matches found.")
                            else:
                                print(f"Top {len(results)} recall result(s):")
                                for item in results:
                                    preview = item.content[:120].replace("\n", " ")
                                    print(f"- {item.memory_id} [{item.kind}] score={item.score:.3f} {preview}")
                            continue
                        if cmd.name == "context":
                            bundle = svc.build_context(
                                ContextBuildInput(
                                    query=cmd.args["query"],
                                    limit=settings.memory.default_recall_limit,
                                )
                            )
                            print(bundle.overview)
                            print(
                                f"Supporting items: {len(bundle.supporting_items)} | "
                                f"Linked records: {len(bundle.linked_records)}"
                            )
                            continue
                        if cmd.name == "inspect":
                            item = svc.inspect_memory(cmd.args["memory_id"])
                            if not item:
                                print(f"Memory {cmd.args['memory_id']} not found.")
                            else:
                                preview = str(item.get("content", ""))[:200].replace("\n", " ")
                                print(
                                    f"Memory {cmd.args['memory_id']}: kind={item.get('kind')} "
                                    f"source={item.get('source')} content={preview}"
                                )
                            continue
                    except Exception as e:
                        print(f"command error: {e}")
                        continue

                if workflow_mode == "memory":
                    result = svc.remember(RememberInput(kind="note", content=text, source="repl", author="user"))
                    print(
                        f"Remembered note as memory {result['memory']['memory_id']} "
                        f"({result['chunk_count']} chunk(s))."
                    )
                    continue

                if llm_enabled:
                    if agent_executor is None:
                        print(
                            "LLM is not available. Use \\llm off to disable LLM mode or check your configuration."
                        )
                        continue
                    result = agent_executor.invoke({"input": text, "chat_history": chat_history})
                    output = result.get("output", "")
                    if output:
                        if log_enabled:
                            log_print("LLM", output)
                        else:
                            print(output)
                    chat_history.extend([HumanMessage(content=text), AIMessage(content=output)])
                else:
                    if log_enabled:
                        log_print("TOOL", text)
                    success, result = execute_cypher_with_smart_columns(
                        cur, conn, text, settings, logger if args.verbose else None
                    )
                    if success:
                        formatted = format_rows(result)
                        if log_enabled:
                            log_print("DB", formatted)
                        else:
                            print_result(result)
                    else:
                        error_msg = str(result) if not isinstance(result, str) else result
                        if log_enabled:
                            log_print("DB", error_msg)
                        else:
                            print(error_msg)
            except KeyboardInterrupt:
                print("\n(Use Ctrl+D or \\q to quit. \\h for list of commands)")
            except EOFError:
                print("\nExiting REPL.")
                break
    finally:
        try:
            cur.close()
        finally:
            conn.close()
