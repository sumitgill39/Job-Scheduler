# Engineering Design Document (EDD)
## Modern Multi-Step Job Execution System V2

**Document Version:** 1.0  
**Created:** 2025-09-01  
**Author:** System Architect  
**Status:** Design Phase

---

## Table of Contents
1. [Executive Summary](#executive-summary)
2. [Problem Statement](#problem-statement)
3. [Current State Analysis](#current-state-analysis)
4. [Requirements](#requirements)
5. [Architecture Overview](#architecture-overview)
6. [Detailed Design](#detailed-design)
7. [Implementation Plan](#implementation-plan)
8. [File Structure](#file-structure)
9. [API Specifications](#api-specifications)
10. [Testing Strategy](#testing-strategy)
11. [Migration Strategy](#migration-strategy)
12. [Risk Assessment](#risk-assessment)

---

## 1. Executive Summary

The current Job Scheduler system suffers from critical execution errors, limited extensibility, and lack of timezone-aware scheduling. This document outlines the design for a modern, multi-step, timezone-based job execution system that addresses current limitations and provides a foundation for future growth.

### Key Objectives:
- **Eliminate execution errors** (`'execution_id'` KeyError and related issues)
- **Enable multi-step jobs** (SQL → PowerShell → Azure DevOps workflows)
- **Implement timezone-based scheduling queues**
- **Create extensible step framework** for future job types
- **Ensure reliable, scalable execution**

---

## 2. Problem Statement

### Current Issues:
1. **Critical Execution Errors**
   - Persistent `'execution_id'` KeyError in job execution
   - Inconsistent dictionary access patterns
   - Unreliable response handling

2. **Limited Job Capabilities**
   - Single-step jobs only (SQL OR PowerShell)
   - No support for complex workflows
   - No Azure DevOps integration

3. **Timezone Limitations**
   - All jobs executed in single timezone context
   - No timezone-specific scheduling queues
   - UTC-only precision timing

4. **Scalability Issues**
   - Monolithic job execution architecture
   - No separation of concerns
   - Difficult to extend for new job types

### Impact:
- **High**: Jobs fail to execute, causing operational disruptions
- **Medium**: Limited workflow capabilities restrict business automation
- **Medium**: Timezone issues affect global scheduling accuracy

---

## 3. Current State Analysis

### Existing Architecture:
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Web Routes    │───▶│  Job Executor   │───▶│  Job Instance   │
│                 │    │                 │    │  (SQL/PS)       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │
         ▼                       ▼
┌─────────────────┐    ┌─────────────────┐
│ Error Handler   │    │  Execution Log  │
│ (Broken)        │    │                 │
└─────────────────┘    └─────────────────┘
```

### Current File Structure:
```
core/
├── job_executor.py      # BROKEN - KeyError issues
├── job_base.py         # Limited single-step execution
├── sql_job.py          # SQL-only execution
├── powershell_job.py   # PowerShell-only execution
└── scheduler_manager.py # Legacy scheduling
```

### Problems Identified:
1. **`job_executor.py:648`** - Dictionary access causing KeyError
2. **Monolithic design** - Hard to extend for new job types  
3. **No timezone queues** - Single execution context
4. **Legacy patterns** - Inconsistent error handling

---

## 4. Requirements

### 4.1 Functional Requirements

#### FR1: Multi-Step Job Execution
- **REQ-001**: Jobs shall support multiple sequential steps
- **REQ-002**: Each step shall be independently configurable
- **REQ-003**: Steps shall support different execution types (SQL, PowerShell, Azure DevOps)
- **REQ-004**: Step execution shall support conditional logic (continue_on_failure)

#### FR2: Timezone-Based Scheduling
- **REQ-005**: System shall maintain separate execution queues per timezone
- **REQ-006**: Jobs shall be scheduled in their specified timezone
- **REQ-007**: Queue workers shall respect timezone-specific timing
- **REQ-008**: System shall support dynamic timezone queue creation

#### FR3: Extensible Step Framework
- **REQ-009**: System shall support plugin-based step types
- **REQ-010**: New step types shall be registerable at runtime
- **REQ-011**: Step types shall implement common interface
- **REQ-012**: Step validation shall be configurable per type

#### FR4: Azure DevOps Integration
- **REQ-013**: System shall support Azure DevOps pipeline triggers
- **REQ-014**: Azure DevOps steps shall support parameter passing
- **REQ-015**: Pipeline execution status shall be trackable
- **REQ-016**: Authentication shall be configurable per organization

#### FR5: Reliable Execution
- **REQ-017**: Job execution shall never fail due to dictionary access errors
- **REQ-018**: All responses shall use safe dictionary access patterns
- **REQ-019**: Execution results shall be consistently formatted
- **REQ-020**: Error handling shall be comprehensive and consistent

### 4.2 Non-Functional Requirements

#### NFR1: Performance
- **REQ-021**: System shall support concurrent job execution across timezones
- **REQ-022**: Job startup time shall be < 5 seconds
- **REQ-023**: System shall handle 100+ concurrent executions
- **REQ-024**: Memory usage shall remain stable under load

#### NFR2: Reliability  
- **REQ-025**: Job execution success rate shall be > 99.9%
- **REQ-026**: System shall recover gracefully from individual step failures
- **REQ-027**: Timezone queues shall be fault-tolerant
- **REQ-028**: Data consistency shall be maintained across failures

#### NFR3: Maintainability
- **REQ-029**: Code shall follow single responsibility principle
- **REQ-030**: Step types shall be independently testable
- **REQ-031**: Configuration shall be externalized
- **REQ-032**: Logging shall be comprehensive and structured

#### NFR4: Scalability
- **REQ-033**: System shall scale horizontally by adding timezone queues
- **REQ-034**: Step execution shall be parallelizable where possible
- **REQ-035**: Resource usage shall be configurable per queue
- **REQ-036**: System shall support graceful degradation

---

## 5. Architecture Overview

### 5.1 High-Level Architecture

```
                             ┌─────────────────────────────────────┐
                             │           SCHEDULER LAYER           │
                             └─────────────────────────────────────┘
                                              │
                             ┌─────────────────────────────────────┐
                             │         TIMEZONE QUEUES             │
                             ├─────────────┬─────────────┬─────────┤
                             │ UTC Queue   │ EU Queue    │ US Queue│
                             │             │             │         │
                             └─────────────┴─────────────┴─────────┘
                                              │
                             ┌─────────────────────────────────────┐
                             │        EXECUTION ENGINE             │
                             └─────────────────────────────────────┘
                                              │
                             ┌─────────────────────────────────────┐
                             │          STEP FACTORY               │
                             └─────────────────────────────────────┘
                                              │
                    ┌─────────────┬─────────────────────┬─────────────────┐
               ┌────▼────┐   ┌────▼────┐         ┌─────▼─────┐        │
               │   SQL   │   │PowerShell│        │Azure DevOps│    ┌──▼──┐
               │  Step   │   │  Step   │         │   Step     │    │ ... │
               └─────────┘   └─────────┘         └───────────┘     └─────┘
```

### 5.2 Component Responsibilities

#### Scheduler Layer
- **Purpose**: High-level job scheduling and coordination
- **Responsibilities**: Job parsing, timezone routing, result aggregation
- **Interface**: REST API endpoints

#### Timezone Queues
- **Purpose**: Timezone-specific job queuing and execution
- **Responsibilities**: Queue management, timing precision, worker coordination
- **Interface**: Async queue operations

#### Execution Engine
- **Purpose**: Core job execution orchestration
- **Responsibilities**: Step sequencing, context management, result collection
- **Interface**: Job execution methods

#### Step Factory
- **Purpose**: Step type management and instantiation
- **Responsibilities**: Step registration, validation, instantiation
- **Interface**: Factory pattern methods

#### Step Types
- **Purpose**: Specific execution implementations
- **Responsibilities**: Type-specific execution logic, result formatting
- **Interface**: Common step interface

---

## 6. Detailed Design

### 6.1 Core Classes

#### 6.1.1 JobDefinition
```python
@dataclass
class JobDefinition:
    job_id: str
    job_name: str
    description: str
    timezone: str
    steps: List[Dict[str, Any]]
    schedule: Optional[Dict[str, Any]] = None
    enabled: bool = True
    max_retries: int = 0
    timeout_seconds: int = 3600
    metadata: Dict[str, Any] = field(default_factory=dict)
```

**Purpose**: Immutable job configuration data structure  
**Responsibilities**: Store job metadata, steps configuration, scheduling parameters

#### 6.1.2 ExecutionStep (Abstract Base)
```python
class ExecutionStep(ABC):
    def __init__(self, step_id: str, step_name: str, config: Dict[str, Any])
    
    @property
    @abstractmethod
    def step_type(self) -> str: ...
    
    @abstractmethod
    async def execute(self, context: Dict[str, Any]) -> StepResult: ...
    
    def validate_config(self) -> List[str]: ...
```

**Purpose**: Common interface for all step types  
**Responsibilities**: Define execution contract, provide validation framework

#### 6.1.3 TimezoneJobQueue
```python
class TimezoneJobQueue:
    def __init__(self, timezone_name: str)
    def add_job(self, job: JobDefinition, scheduled_time: datetime, priority: int = 0)
    async def start(self)
    async def stop(self) 
    async def _worker(self)  # Private worker coroutine
    async def _execute_job(self, job: JobDefinition) -> JobExecutionResult
```

**Purpose**: Timezone-specific job queue management  
**Responsibilities**: Queue operations, timing precision, job execution coordination

#### 6.1.4 ModernExecutionEngine
```python
class ModernExecutionEngine:
    def __init__(self)
    async def start(self)
    async def stop(self)
    def add_timezone_queue(self, timezone_name: str)
    async def schedule_job(self, job: JobDefinition, scheduled_time: datetime, priority: int = 0)
    async def execute_job_now(self, job: JobDefinition) -> JobExecutionResult
    def get_queue_status(self) -> Dict[str, Dict[str, Any]]
```

**Purpose**: Central execution engine coordination  
**Responsibilities**: Queue management, immediate execution, status reporting

### 6.2 Step Type Implementations

#### 6.2.1 SqlStep
```python
class SqlStep(ExecutionStep):
    @property
    def step_type(self) -> str: return "sql"
    
    async def execute(self, context: Dict[str, Any]) -> StepResult:
        # SQL execution logic with connection management
        # Thread pool execution for blocking database operations
        # Result formatting and metadata collection
```

**Configuration Parameters**:
- `query`: SQL query string
- `connection_name`: Database connection identifier  
- `timeout`: Query timeout in seconds
- `max_rows`: Maximum result rows
- `parameters`: Query parameters

#### 6.2.2 PowerShellStep  
```python
class PowerShellStep(ExecutionStep):
    @property
    def step_type(self) -> str: return "powershell"
    
    async def execute(self, context: Dict[str, Any]) -> StepResult:
        # PowerShell execution logic
        # Script file or inline script support
        # Parameter substitution and validation
```

**Configuration Parameters**:
- `script`: Inline PowerShell script
- `script_path`: Path to PowerShell script file
- `parameters`: Script parameters
- `execution_policy`: PowerShell execution policy
- `timeout`: Script timeout

#### 6.2.3 AzureDevOpsStep
```python
class AzureDevOpsStep(ExecutionStep):
    @property
    def step_type(self) -> str: return "azure_devops"
    
    async def execute(self, context: Dict[str, Any]) -> StepResult:
        # Azure DevOps API integration
        # Pipeline triggering and status monitoring
        # Authentication and error handling
```

**Configuration Parameters**:
- `organization`: Azure DevOps organization
- `project`: Project name
- `pipeline_id`: Pipeline identifier
- `branch`: Target branch
- `parameters`: Pipeline parameters
- `wait_for_completion`: Whether to wait for pipeline completion

### 6.3 Data Flow

#### 6.3.1 Job Execution Flow
```
1. API Request → ModernJobAPI.execute_job_immediately()
2. Job Parsing → JobDefinition creation
3. Engine Routing → ModernExecutionEngine.execute_job_now()  
4. Step Creation → StepFactory.create_step() for each step
5. Step Execution → step.execute() with context
6. Result Collection → JobExecutionResult aggregation
7. Response Formation → API response formatting
```

#### 6.3.2 Scheduled Job Flow
```
1. Schedule Request → ModernJobAPI.schedule_job()
2. Timezone Resolution → TimezoneJobQueue selection/creation
3. Queue Addition → queue.add_job() with priority
4. Worker Processing → queue._worker() continuous loop
5. Timed Execution → Timezone-aware execution timing
6. Result Storage → Result persistence and logging
```

---

## 7. Implementation Plan

### 7.1 Phase 1: Foundation (Week 1)
#### Tasks:
1. **Create core data structures**
   - `JobDefinition` dataclass
   - `StepResult` and `JobExecutionResult` classes
   - Status enums

2. **Implement base step framework**
   - `ExecutionStep` abstract base class
   - `StepFactory` with registration system
   - Common validation patterns

3. **Basic step implementations**
   - `SqlStep` with connection management
   - `PowerShellStep` with script execution
   - Comprehensive error handling

#### Deliverables:
- `core/v2/data_models.py`
- `core/v2/step_framework.py`
- `core/v2/step_implementations.py`
- Unit tests for all components

### 7.2 Phase 2: Execution Engine (Week 2)
#### Tasks:
1. **Implement timezone queue system**
   - `TimezoneJobQueue` with priority queuing
   - Async worker implementation
   - Queue lifecycle management

2. **Create execution engine**
   - `ModernExecutionEngine` coordination
   - Job context management
   - Result aggregation

3. **Add immediate execution support**
   - Synchronous execution for API calls
   - Thread pool management
   - Resource cleanup

#### Deliverables:
- `core/v2/timezone_queue.py`
- `core/v2/execution_engine.py`
- `core/v2/execution_context.py`
- Integration tests

### 7.3 Phase 3: API Integration (Week 3)
#### Tasks:
1. **Create modern API layer**
   - `ModernJobAPI` class
   - Flask route integration
   - Request/response handling

2. **Implement scheduling endpoints**
   - Immediate execution API
   - Scheduled execution API
   - Status and monitoring APIs

3. **Add Azure DevOps support**
   - `AzureDevOpsStep` implementation
   - API authentication
   - Pipeline monitoring

#### Deliverables:
- `core/v2/modern_job_api.py`
- `web_ui/v2_routes.py`
- `core/v2/azure_devops_step.py`
- API documentation

### 7.4 Phase 4: Migration & Testing (Week 4)
#### Tasks:
1. **Legacy system migration**
   - Data format conversion utilities
   - Backward compatibility layer
   - Migration scripts

2. **Comprehensive testing**
   - End-to-end test suite
   - Load testing framework
   - Error scenario testing

3. **Production deployment**
   - Configuration management
   - Monitoring setup
   - Rollback procedures

#### Deliverables:
- `tools/migration/`
- `tests/e2e/`
- `deploy/production/`
- Operations documentation

---

## 8. File Structure

### 8.1 New File Organization
```
job_scheduler/
├── core/
│   ├── v2/                           # NEW: Modern execution system
│   │   ├── __init__.py
│   │   ├── data_models.py            # JobDefinition, Results, Enums
│   │   ├── step_framework.py         # ExecutionStep, StepFactory
│   │   ├── step_implementations.py   # SQL, PowerShell, AzureDevOps steps
│   │   ├── timezone_queue.py         # TimezoneJobQueue implementation  
│   │   ├── execution_engine.py       # ModernExecutionEngine
│   │   ├── execution_context.py      # Job execution context management
│   │   ├── modern_job_api.py         # API layer for new system
│   │   └── azure_devops_client.py    # Azure DevOps API integration
│   │
│   ├── legacy/                       # MOVED: Current broken system
│   │   ├── job_executor.py           # BROKEN - Moved for reference
│   │   ├── job_base.py              # Legacy base classes
│   │   ├── sql_job.py               # Legacy SQL implementation
│   │   └── powershell_job.py        # Legacy PowerShell implementation
│   │
│   └── common/                       # SHARED: Common utilities
│       ├── connection_manager.py     # Database connections
│       ├── windows_utils.py          # PowerShell utilities
│       └── validation.py            # Input validation
│
├── web_ui/
│   ├── v2_routes.py                  # NEW: Modern API endpoints
│   ├── routes.py                     # UPDATED: Migration wrapper routes
│   └── templates/
│       └── v2/                       # NEW: Modern UI templates
│           ├── multi_step_job.html   # Multi-step job creation
│           ├── timezone_queues.html  # Queue status dashboard
│           └── azure_devops.html     # Azure DevOps configuration
│
├── config/
│   ├── step_types.yaml              # NEW: Step type configurations
│   ├── timezone_queues.yaml         # NEW: Timezone queue settings
│   └── azure_devops.yaml            # NEW: Azure DevOps settings
│
├── tools/
│   ├── migration/                    # NEW: Migration utilities
│   │   ├── convert_legacy_jobs.py   # Legacy job conversion
│   │   ├── test_migration.py        # Migration testing
│   │   └── rollback_utilities.py    # Rollback tools
│   │
│   └── testing/                      # NEW: Testing utilities
│       ├── load_test.py             # Load testing
│       ├── mock_services.py         # Mock external services
│       └── test_data_generator.py   # Test data generation
│
├── tests/
│   ├── unit/
│   │   ├── test_v2_steps.py         # NEW: Step unit tests
│   │   ├── test_timezone_queue.py   # NEW: Queue unit tests
│   │   └── test_execution_engine.py # NEW: Engine unit tests
│   │
│   ├── integration/
│   │   ├── test_job_execution.py    # NEW: End-to-end execution tests
│   │   ├── test_api_endpoints.py    # NEW: API integration tests
│   │   └── test_azure_devops.py     # NEW: Azure DevOps integration tests
│   │
│   └── load/
│       ├── test_concurrent_jobs.py  # NEW: Concurrency testing
│       └── test_timezone_queues.py  # NEW: Queue performance tests
│
├── docs/
│   ├── EDD_JobExecution_V2.md       # THIS DOCUMENT
│   ├── API_Reference_V2.md          # NEW: API documentation
│   ├── Step_Development_Guide.md    # NEW: Custom step development
│   ├── Migration_Guide.md           # NEW: Legacy migration guide
│   └── Operations_Manual_V2.md      # NEW: Operations procedures
│
└── ReadmeV2.md                      # NEW: Updated project documentation
```

### 8.2 File Responsibilities

#### Core V2 Files:

**`data_models.py`**
- `JobDefinition` - Job configuration data structure
- `StepResult` - Individual step execution result
- `JobExecutionResult` - Complete job execution result  
- `JobStatus`, `StepStatus` - Status enumerations
- Serialization/deserialization utilities

**`step_framework.py`**
- `ExecutionStep` - Abstract base class for all steps
- `StepFactory` - Step type registration and instantiation
- `StepValidationError` - Step-specific exceptions
- Common step utilities and helpers

**`step_implementations.py`**
- `SqlStep` - SQL query execution step
- `PowerShellStep` - PowerShell script execution step  
- `AzureDevOpsStep` - Azure DevOps pipeline trigger step
- `HttpStep` - HTTP request step (future)
- `FileOperationStep` - File operation step (future)

**`timezone_queue.py`**
- `TimezoneJobQueue` - Timezone-specific job queue
- `QueueWorker` - Async job processing worker
- `PriorityScheduler` - Priority-based job scheduling
- Queue metrics and monitoring

**`execution_engine.py`**
- `ModernExecutionEngine` - Central execution coordinator
- `ExecutionManager` - Job execution lifecycle management
- `ResourceManager` - System resource management
- Engine configuration and monitoring

**`execution_context.py`**
- `JobExecutionContext` - Job execution context container
- `StepExecutionContext` - Step-specific context
- `ContextVariableManager` - Context variable management
- Context serialization utilities

**`modern_job_api.py`**
- `ModernJobAPI` - Main API interface class
- Request parsing and validation
- Response formatting utilities  
- Error handling and logging

**`azure_devops_client.py`**
- `AzureDevOpsClient` - Azure DevOps API client
- Authentication management
- Pipeline operation APIs
- Status monitoring utilities

---

## 9. API Specifications

### 9.1 New V2 API Endpoints

#### 9.1.1 Execute Job Immediately
**Endpoint**: `POST /api/v2/jobs/execute`

**Request Body**:
```json
{
  "job": {
    "id": "data-pipeline-001",
    "name": "Daily Data Pipeline",
    "description": "Extract, transform, and deploy data",
    "timezone": "America/New_York",
    "timeout_seconds": 3600,
    "steps": [
      {
        "id": "extract",
        "name": "Extract Data",
        "type": "sql",
        "query": "SELECT * FROM source_table WHERE date = CURRENT_DATE",
        "connection_name": "warehouse",
        "timeout": 300
      },
      {
        "id": "process",
        "name": "Process Data",
        "type": "powershell",
        "script_path": "scripts/process-data.ps1",
        "parameters": {
          "InputPath": "data/raw",
          "OutputPath": "data/processed"
        },
        "continue_on_failure": false
      },
      {
        "id": "deploy",
        "name": "Deploy to Production",
        "type": "azure_devops",
        "organization": "mycompany",
        "project": "data-platform",
        "pipeline_id": "123",
        "branch": "main",
        "parameters": {
          "Environment": "production",
          "DataPath": "data/processed"
        },
        "wait_for_completion": true
      }
    ]
  }
}
```

**Response**:
```json
{
  "success": true,
  "message": "Job Daily Data Pipeline completed successfully",
  "execution_id": "exec_20250901_143022_001",
  "job_id": "data-pipeline-001",
  "job_name": "Daily Data Pipeline",
  "status": "success",
  "timezone": "America/New_York",
  "start_time": "2025-09-01T14:30:22.123456Z",
  "end_time": "2025-09-01T14:32:45.789012Z",
  "duration_seconds": 143.67,
  "steps": [
    {
      "step_id": "extract",
      "step_name": "Extract Data", 
      "step_type": "sql",
      "status": "success",
      "duration_seconds": 45.23,
      "output": "Query executed successfully. 1,234 rows returned.",
      "metadata": {
        "query": "SELECT * FROM source_table WHERE date = CURRENT_DATE",
        "connection_name": "warehouse",
        "row_count": 1234
      }
    },
    {
      "step_id": "process",
      "step_name": "Process Data",
      "step_type": "powershell", 
      "status": "success",
      "duration_seconds": 67.89,
      "output": "Processing completed. 1,234 records processed successfully.",
      "metadata": {
        "script_path": "scripts/process-data.ps1",
        "parameters": {"InputPath": "data/raw", "OutputPath": "data/processed"}
      }
    },
    {
      "step_id": "deploy",
      "step_name": "Deploy to Production",
      "step_type": "azure_devops",
      "status": "success", 
      "duration_seconds": 30.55,
      "output": "Pipeline #456 completed successfully",
      "metadata": {
        "organization": "mycompany",
        "project": "data-platform",
        "pipeline_id": "123",
        "run_id": "456",
        "branch": "main"
      }
    }
  ],
  "step_count": 3,
  "successful_steps": 3,
  "failed_steps": 0
}
```

#### 9.1.2 Schedule Job
**Endpoint**: `POST /api/v2/jobs/schedule`

**Request Body**:
```json
{
  "job": {
    "id": "nightly-backup",
    "name": "Nightly Database Backup",
    "timezone": "UTC",
    "steps": [
      {
        "id": "backup",
        "name": "Backup Database",
        "type": "sql", 
        "query": "BACKUP DATABASE MyDB TO DISK = 'backup.bak'",
        "connection_name": "production"
      }
    ]
  },
  "scheduled_time": "2025-09-02T02:00:00Z"
}
```

**Response**:
```json
{
  "success": true,
  "message": "Job Nightly Database Backup scheduled successfully", 
  "job_id": "nightly-backup",
  "scheduled_time": "2025-09-02T02:00:00Z",
  "timezone": "UTC",
  "status": "scheduled"
}
```

#### 9.1.3 Get Execution Status
**Endpoint**: `GET /api/v2/execution/status`

**Response**:
```json
{
  "success": true,
  "engine_started": true,
  "timezone_queues": {
    "UTC": {
      "timezone": "UTC",
      "queue_size": 3,
      "active_executions": 1,
      "running": true
    },
    "America/New_York": {
      "timezone": "America/New_York", 
      "queue_size": 0,
      "active_executions": 2,
      "running": true
    },
    "Europe/London": {
      "timezone": "Europe/London",
      "queue_size": 1, 
      "active_executions": 0,
      "running": true
    }
  },
  "total_queues": 3,
  "total_active_executions": 3,
  "timestamp": "2025-09-01T14:30:22.123456Z"
}
```

#### 9.1.4 Get Available Step Types
**Endpoint**: `GET /api/v2/steps/types`

**Response**:
```json
{
  "success": true,
  "step_types": [
    "sql",
    "powershell", 
    "azure_devops",
    "http",
    "file_operation"
  ],
  "count": 5,
  "timestamp": "2025-09-01T14:30:22.123456Z"
}
```

### 9.2 Legacy API Compatibility

#### 9.2.1 Updated Run Job Endpoint
**Endpoint**: `POST /api/jobs/<job_id>/run`

The existing endpoint will be updated to use the new execution engine internally while maintaining backward compatibility:

**Current Request**: `POST /api/jobs/abc123/run`

**Updated Response** (maintains compatibility):
```json
{
  "success": true,
  "message": "Job executed with status: success",
  "execution_id": "exec_20250901_143022_001", 
  "status": "success",
  "duration_seconds": 45.23,
  "output": "Job executed successfully via modern engine",
  "start_time": "2025-09-01T14:30:22.123456Z",
  "end_time": "2025-09-01T14:32:45.789012Z"
}
```

**Internal Flow**:
1. Fetch job data using existing job_manager
2. Convert legacy job format to JobDefinition
3. Execute using ModernExecutionEngine
4. Convert JobExecutionResult back to legacy response format
5. Return compatible response

---

## 10. Testing Strategy

### 10.1 Unit Testing

#### Test Coverage Requirements:
- **Minimum 90% code coverage** for core execution logic
- **100% coverage** for critical path methods (job execution, step execution)
- **Comprehensive error scenario testing**

#### Key Test Cases:

**Step Framework Tests** (`test_v2_steps.py`):
- Step factory registration and instantiation
- Step configuration validation
- Step execution with various inputs
- Step error handling and recovery
- Context passing between steps

**Timezone Queue Tests** (`test_timezone_queue.py`):
- Queue creation and lifecycle management  
- Job scheduling with different priorities
- Timezone-aware timing precision
- Worker thread management
- Queue metrics and monitoring

**Execution Engine Tests** (`test_execution_engine.py`):
- Job parsing and validation
- Multi-step execution coordination
- Resource management and cleanup
- Error propagation and handling
- Result aggregation and formatting

### 10.2 Integration Testing

#### API Integration Tests (`test_api_endpoints.py`):
- V2 API endpoint functionality
- Request/response format validation
- Error handling and status codes
- Authentication and authorization
- Rate limiting and throttling

#### Job Execution Tests (`test_job_execution.py`):
- End-to-end job execution flow
- Multi-step job coordination
- Step interdependency handling
- Error recovery and retry logic
- Result persistence and retrieval

#### Azure DevOps Tests (`test_azure_devops.py`):
- Pipeline trigger functionality
- Authentication handling
- Parameter passing and validation
- Status monitoring and completion
- Error handling for API failures

### 10.3 Load Testing

#### Concurrency Tests (`test_concurrent_jobs.py`):
- 100+ concurrent job executions
- Multiple timezone queue coordination
- Resource contention handling  
- Memory usage under load
- Performance degradation thresholds

#### Queue Performance Tests (`test_timezone_queues.py`):
- Queue throughput measurement
- Priority handling under load
- Worker scaling effectiveness
- Memory usage per queue
- Latency distribution analysis

### 10.4 Error Scenario Testing

#### Critical Error Scenarios:
1. **Database connection failures during SQL steps**
2. **PowerShell execution timeouts and memory issues**
3. **Azure DevOps API authentication failures**
4. **Network connectivity issues during external calls**
5. **System resource exhaustion (memory, disk, CPU)**
6. **Timezone queue worker crashes and recovery**
7. **Malformed job configuration handling**
8. **Concurrent access to shared resources**

#### Recovery Testing:
- Graceful degradation scenarios
- Queue worker restart procedures
- Job state recovery after system crashes
- Partial execution recovery and continuation

---

## 11. Migration Strategy

### 11.1 Migration Phases

#### Phase 1: Parallel Operation (2 weeks)
- **Objective**: Run both systems simultaneously
- **Approach**: 
  - Deploy V2 system alongside legacy system
  - Route new jobs to V2, existing jobs remain on legacy
  - Compare execution results for validation
  - Monitor performance and stability

#### Phase 2: Gradual Migration (4 weeks)  
- **Objective**: Migrate existing jobs to V2 system
- **Approach**:
  - Convert legacy job definitions to V2 format
  - Migrate jobs in batches based on criticality
  - Maintain rollback capability for each batch
  - Monitor execution success rates

#### Phase 3: Legacy Deprecation (2 weeks)
- **Objective**: Complete transition to V2 system  
- **Approach**:
  - Redirect all job execution to V2 system
  - Maintain legacy APIs for backward compatibility  
  - Archive legacy system components
  - Update documentation and procedures

### 11.2 Data Migration

#### Job Definition Conversion:
```python
# Legacy Format
{
  "job_id": "sql-job-001",
  "name": "Daily Report",
  "job_type": "sql", 
  "sql_query": "SELECT * FROM reports",
  "connection_name": "main_db",
  "timeout": 300
}

# V2 Format  
{
  "id": "sql-job-001",
  "name": "Daily Report",
  "timezone": "UTC",
  "steps": [
    {
      "id": "main_step",
      "name": "Generate Report",
      "type": "sql",
      "query": "SELECT * FROM reports", 
      "connection_name": "main_db",
      "timeout": 300
    }
  ]
}
```

#### Migration Utilities (`tools/migration/convert_legacy_jobs.py`):
- Automated job definition conversion
- Configuration validation and error reporting
- Batch processing with progress tracking
- Rollback capability for failed conversions

### 11.3 Rollback Procedures

#### Rollback Triggers:
1. **Execution success rate drops below 95%**
2. **System performance degradation > 50%**
3. **Critical job failures in production**
4. **Unresolvable compatibility issues**

#### Rollback Process:
1. **Immediate**: Stop V2 job scheduling
2. **Traffic redirect**: Route all jobs back to legacy system  
3. **Data consistency**: Ensure job state consistency
4. **Investigation**: Analyze failure causes
5. **Recovery planning**: Plan corrective actions

### 11.4 Compatibility Maintenance

#### Legacy API Support:
- Maintain existing `/api/jobs/<job_id>/run` endpoint
- Convert legacy requests to V2 format internally
- Transform V2 responses back to legacy format
- Preserve all existing response fields

#### Configuration Compatibility:
- Support both legacy and V2 configuration formats
- Automatic format detection and conversion
- Validation for both formats
- Migration warnings and guidance

---

## 12. Risk Assessment

### 12.1 High-Risk Items

#### RISK-001: Execution Engine Stability
- **Risk**: V2 execution engine introduces new failure modes
- **Impact**: High - Job execution failures affect business operations
- **Mitigation**: 
  - Comprehensive testing before deployment
  - Gradual rollout with monitoring
  - Immediate rollback procedures
  - 24/7 monitoring and alerting

#### RISK-002: Azure DevOps Integration Complexity  
- **Risk**: Azure DevOps API integration introduces external dependencies
- **Impact**: Medium - New job types may be unreliable
- **Mitigation**:
  - Extensive integration testing
  - Mock service testing
  - Circuit breaker patterns
  - Graceful degradation for API failures

#### RISK-003: Performance Regression
- **Risk**: V2 system may be slower than legacy system
- **Impact**: Medium - Slower job execution affects scheduling
- **Mitigation**:
  - Performance benchmarking before deployment
  - Load testing with realistic workloads
  - Performance monitoring and alerting
  - Resource optimization based on metrics

### 12.2 Medium-Risk Items

#### RISK-004: Migration Data Loss
- **Risk**: Job definitions may be lost during migration
- **Impact**: Medium - Jobs may need to be recreated manually  
- **Mitigation**:
  - Complete backup before migration
  - Incremental migration with validation
  - Rollback procedures for each batch
  - Data integrity verification

#### RISK-005: Timezone Precision Issues
- **Risk**: Timezone calculations may be incorrect
- **Impact**: Medium - Jobs may execute at wrong times
- **Mitigation**:
  - Comprehensive timezone testing
  - UTC precision validation
  - Daylight saving time edge case testing
  - Monitoring for timing drift

#### RISK-006: Resource Consumption
- **Risk**: V2 system may use more system resources
- **Impact**: Medium - May affect system performance
- **Mitigation**:
  - Resource usage monitoring
  - Configurable resource limits
  - Automatic resource management
  - Scaling recommendations

### 12.3 Low-Risk Items

#### RISK-007: Configuration Complexity
- **Risk**: V2 configuration format may be too complex
- **Impact**: Low - Users may find it difficult to create jobs
- **Mitigation**:
  - Comprehensive documentation  
  - User-friendly UI for job creation
  - Configuration validation and guidance
  - Migration tools for existing jobs

#### RISK-008: Learning Curve
- **Risk**: Operations team needs to learn new system
- **Impact**: Low - May slow initial adoption
- **Mitigation**:
  - Training documentation and sessions
  - Gradual feature introduction
  - Backward compatibility maintenance  
  - Support during transition period

---

## 13. Success Metrics

### 13.1 Technical Metrics

#### Execution Reliability:
- **Job execution success rate**: > 99.9%
- **Zero `'execution_id'` errors**: 0 occurrences
- **Step execution reliability**: > 99.5% per step
- **System uptime**: > 99.9%

#### Performance Metrics:
- **Job startup time**: < 5 seconds average
- **Step execution overhead**: < 2 seconds per step
- **Concurrent execution capacity**: > 100 jobs
- **Memory usage**: Stable under load

#### Scalability Metrics:
- **Timezone queue count**: Support 20+ timezones
- **Queue throughput**: > 1000 jobs/hour per queue
- **Worker scaling**: Linear performance improvement
- **Resource efficiency**: < 10% overhead vs legacy

### 13.2 Business Metrics

#### Operational Efficiency:
- **Job creation time**: 50% reduction vs legacy
- **Error diagnosis time**: 75% reduction vs legacy  
- **System maintenance time**: 60% reduction vs legacy
- **New job type deployment**: < 1 week

#### User Experience:
- **Job configuration complexity**: Simplified multi-step creation
- **Error message clarity**: 90% of errors self-explanatory
- **Feature adoption rate**: 80% of users adopting new features
- **Support ticket reduction**: 50% fewer execution-related tickets

### 13.3 Monitoring and Alerting

#### Critical Alerts:
- Job execution failure rate > 1%
- System memory usage > 85%
- Queue processing delays > 5 minutes
- External API failures (Azure DevOps) > 5%

#### Performance Monitoring:
- Real-time execution metrics dashboard
- Timezone queue status monitoring
- Resource utilization trending
- Error rate and pattern analysis

---

## 14. Conclusion

This Engineering Design Document outlines a comprehensive solution for the Job Scheduler's execution system problems. The V2 architecture addresses critical reliability issues while providing extensive new capabilities for multi-step, timezone-aware job execution.

### Key Benefits of V2 System:
1. **Eliminates critical execution errors** through proper error handling
2. **Enables complex workflows** with multi-step job support
3. **Provides timezone precision** with dedicated queue management
4. **Ensures future extensibility** with plugin-based step framework
5. **Maintains backward compatibility** during migration period

### Implementation Success Factors:
1. **Comprehensive testing** at all levels (unit, integration, load)
2. **Gradual migration strategy** with rollback capabilities  
3. **Continuous monitoring** throughout deployment
4. **Team training and documentation** for smooth adoption
5. **Performance optimization** based on real-world usage

The proposed solution provides a solid foundation for the Job Scheduler's future growth while immediately addressing current operational issues.

---

**Document Status**: Ready for Implementation Review  
**Next Steps**: 
1. Review and approval by architecture team
2. Resource allocation and timeline confirmation
3. Detailed implementation planning
4. Development team assignment and kickoff