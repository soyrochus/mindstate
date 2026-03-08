## ADDED Requirements

### Requirement: `MS_AUTO_CONTEXTUALIZE_KINDS` configures kind-based auto-contextualization
`get_settings()` SHALL read `MS_AUTO_CONTEXTUALIZE_KINDS` as a comma-separated list of memory kinds. The default value SHALL be `decision,architecture_note,resolved_blocker,task,observation,claim`. The setting SHALL be accessible on the `Settings` object and used by `MindStateService` to determine automatic job enqueuing.

#### Scenario: Default auto-kinds when unset
- **WHEN** `MS_AUTO_CONTEXTUALIZE_KINDS` is not set in the environment
- **THEN** `settings.contextualization.auto_kinds` equals `{"decision", "architecture_note", "resolved_blocker", "task", "observation", "claim"}`

#### Scenario: Custom kinds override defaults
- **WHEN** `MS_AUTO_CONTEXTUALIZE_KINDS=note,summary` is set
- **THEN** `settings.contextualization.auto_kinds` equals `{"note", "summary"}` and the defaults are not included

### Requirement: `MS_CONTEXTUALIZE_ENABLED` is a master switch
`get_settings()` SHALL read `MS_CONTEXTUALIZE_ENABLED` as a boolean (values `true`/`false`, case-insensitive). Default is `true`. When `false`, no contextualization jobs SHALL be created by any code path.

#### Scenario: Enabled by default
- **WHEN** `MS_CONTEXTUALIZE_ENABLED` is not set
- **THEN** `settings.contextualization.enabled` is `True`

#### Scenario: Disabled via environment variable
- **WHEN** `MS_CONTEXTUALIZE_ENABLED=false` is set
- **THEN** `settings.contextualization.enabled` is `False`

### Requirement: `MS_CONTEXTUALIZE_CONFIDENCE_THRESHOLD` sets entity inclusion cutoff
`get_settings()` SHALL read `MS_CONTEXTUALIZE_CONFIDENCE_THRESHOLD` as a float. Default is `0.85`. Entities with LLM-assigned confidence below this value SHALL be excluded from resolution and graph writes.

#### Scenario: Default confidence threshold
- **WHEN** `MS_CONTEXTUALIZE_CONFIDENCE_THRESHOLD` is not set
- **THEN** `settings.contextualization.confidence_threshold` is `0.85`

#### Scenario: Override confidence threshold
- **WHEN** `MS_CONTEXTUALIZE_CONFIDENCE_THRESHOLD=0.7` is set
- **THEN** `settings.contextualization.confidence_threshold` is `0.7`

### Requirement: `MS_CONTEXTUALIZE_MERGE_THRESHOLD` sets embedding similarity cutoff for entity resolution
`get_settings()` SHALL read `MS_CONTEXTUALIZE_MERGE_THRESHOLD` as a float. Default is `0.92`. Entity resolution step 2 (embedding similarity) SHALL only auto-merge when cosine similarity exceeds this value.

#### Scenario: Default merge threshold
- **WHEN** `MS_CONTEXTUALIZE_MERGE_THRESHOLD` is not set
- **THEN** `settings.contextualization.merge_threshold` is `0.92`

### Requirement: `MS_CONTEXTUALIZE_MAX_ENTITIES_PER_ITEM` caps LLM entity extraction
`get_settings()` SHALL read `MS_CONTEXTUALIZE_MAX_ENTITIES_PER_ITEM` as an integer. Default is `12`. The entity recognition stage SHALL retain at most this many entities per item, selecting by descending confidence.

#### Scenario: Default entity cap
- **WHEN** `MS_CONTEXTUALIZE_MAX_ENTITIES_PER_ITEM` is not set
- **THEN** `settings.contextualization.max_entities_per_item` is `12`
