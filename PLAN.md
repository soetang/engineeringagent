# Agents Package Implementation Plan

## Overview
Build an Agents Package following the quality domain pattern, starting with a Codex CLI implementation.

## Structure
```
src/developer/agents/
├── __init__.py
├── protocol.py          # AgentProtocol interface
├── models.py            # Pydantic output models
└── adapters/
    ├── __init__.py
    └── codex_adapter.py # Codex CLI implementation
```

## Key Components

### 1. Protocol (`protocol.py`)
```python
from typing import Protocol, Type, TypeVar, Union
from pydantic import BaseModel

T = TypeVar('T', bound=Union[BaseModel, str])

class AgentProtocol(Protocol):
    def run_agent(self, prompt: str, output_format: Type[T] = str,
                 model: str = None, profile: str = None) -> T:
        """Execute agent with prompt, return structured output or string"""
        ...
```

### 2. Models (`models.py`)
- **No predefined models** - users provide their own pydantic models
- Example user models: `MathOutput`, `FileListOutput`, etc.
- Agent works with ANY pydantic model the user defines

### 3. Codex CLI Adapter (`adapters/codex_adapter.py`)
- Implements `AgentProtocol`
- Uses `subprocess.run()` to execute `codex exec` commands
- Generates JSON schemas dynamically from pydantic models
- Parses structured JSON output into requested pydantic model
- Handles errors and timeouts

## Codex CLI Behavior

**Command Pattern:**
```bash
codex exec "prompt" --output-schema /tmp/schema.json
```

**Key Options:**
- `--output-schema`: JSON schema for structured output

**Schema Requirements:**
- Must have `"additionalProperties": false`
- **All properties must be in `"required"` array** (even optional fields)
- Simple types work best (string, boolean, number, arrays)
- Complex nested structures may need flattening

## Implementation Steps

1. **Create package structure**
   - `mkdir -p src/developer/agents/adapters`
   - Create `__init__.py` files

2. **Implement protocol**
   - Simple interface with `run_agent()` method
   - Support both string output (default) and pydantic models
   - Generic type support for output formats

3. **Create pydantic models**
   - Base `AgentOutput` model
   - Extended `CodexOutput` model

4. **Implement codex adapter**
   - Detect output format type (str vs BaseModel)
   - For string output: use basic `codex exec "prompt"`
   - For ANY pydantic model: 
     - Generate JSON schema with **all fields marked as required** (Codex requirement)
     - Handle optional fields by providing default values in schema
     - Use `--output-schema` with generated schema
   - Command execution with subprocess
   - JSON parsing for model outputs, direct string return for str
   - Error handling for both cases
   - **No predefined models** - works with any user-provided pydantic model

5. **Test implementation**
   - String output tests
   - Pydantic model output tests
   - Different model types
   - Error cases for both modes

## Example Usage

```python
from pydantic import BaseModel
from developer.agents.adapters.codex_adapter import CodexAdapter

# User defines their own models
class MathOutput(BaseModel):
    result: int
    success: bool = True  # Optional field with default

class FileListOutput(BaseModel):
    files: list[str]
    count: int
    error: str = ""  # Optional field with default

adapter = CodexAdapter()

# String output (default) - no model needed
result = adapter.run_agent(prompt="What is 2+2?")
print(result)  # "4"

# User-defined model output
math_result = adapter.run_agent(
    prompt="Calculate 5 + 3",
    output_format=MathOutput
)
print(math_result.result)  # 8
print(math_result.success)  # True

# Another user-defined model
file_result = adapter.run_agent(
    prompt="List Python files in current directory",
    output_format=FileListOutput
)
print(file_result.files)  # ["main.py", "utils.py", ...]
print(file_result.count)  # 5
```

## Testing Strategy

1. **String Output Tests**:
   - Simple prompts returning strings
   - Error cases with string output
   - Edge cases (empty output, special characters)

2. **Pydantic Model Tests**:
   - Schema generation with **all fields required** (Codex constraint)
   - JSON parsing and model validation
   - Various model structures (simple, nested, lists, etc.)
   - Handling of optional fields with default values
   - Custom user models (not predefined ones)
   - Edge cases: empty models, single-field models, complex types

3. **Integration Tests**:
   - Actual codex CLI execution
   - Both string and model modes
   - Performance and timeout handling

4. **Error Handling**:
   - Invalid prompts
   - Schema generation failures
   - CLI execution errors
   - JSON parsing errors

## Dependencies

- Python 3.8+
- Pydantic
- Subprocess (standard library)
- Codex CLI (must be installed and available in PATH)

## Future Extensions

- Additional agent types (LLM APIs, local models)
- Streaming output support
- Advanced error recovery
- Performance optimizations