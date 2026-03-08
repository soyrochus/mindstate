import pytest

from mindstate.commands import CommandParseError, parse_slash_command


def test_parse_contextualize_variants():
    assert parse_slash_command(r"\contextualize").args == {"n": 1}
    assert parse_slash_command(r"\contextualize 5").args == {"n": 5}
    assert parse_slash_command(r"\contextualize --id 11111111-1111-1111-1111-111111111111").args == {
        "ids": ["11111111-1111-1111-1111-111111111111"]
    }


def test_parse_memory_commands_and_mode():
    cmd = parse_slash_command(r"\remember note | hello world")
    assert cmd.name == "remember"
    assert cmd.args == {"kind": "note", "content": "hello world"}

    assert parse_slash_command(r"\mode memory").args == {"mode": "memory"}
    assert parse_slash_command(r"\recall alpha").args == {"query": "alpha"}
    assert parse_slash_command(r"\context release prep").args == {"query": "release prep"}
    assert parse_slash_command(r"\inspect abc").args == {"memory_id": "abc"}


def test_parse_invalid_command_usage():
    with pytest.raises(CommandParseError):
        parse_slash_command(r"\log maybe")
    with pytest.raises(CommandParseError):
        parse_slash_command(r"\contextualize --id")
    with pytest.raises(CommandParseError):
        parse_slash_command(r"\unknown")
