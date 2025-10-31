# AWS SAM CLI Architecture Diagrams

## Clean Architecture Overview

```mermaid
graph TB
    subgraph "Presentation Layer"
        CLI[CLI Commands<br/>Click Framework]
        API[Local API Services<br/>Flask/HTTP]
    end
    
    subgraph "Application Layer"
        CM[Command Managers]
        SM[Service Managers]
        EH[Event Handlers]
    end
    
    subgraph "Domain Layer"
        FP[Function Providers]
        RT[Runtime Models]
        CF[Configuration]
        EV[Environment Variables]
    end
    
    subgraph "Infrastructure Layer"
        DC[Docker Container<br/>Management]
        FS[File System]
        NET[Network Services]
        LOG[Logging]
    end
    
    CLI --> CM
    API --> SM
    CM --> FP
    SM --> FP
    FP --> RT
    RT --> DC
    EH --> LOG
    CF --> EV
    DC --> NET
    DC --> FS
```

## Function URLs Feature Architecture

```mermaid
graph LR
    subgraph "Client"
        HTTP[HTTP Request]
    end
    
    subgraph "Function URL Service"
        PM[Port Manager]
        FUM[Function URL Manager]
        
        subgraph "Per Function"
            FS1[Flask Server 1<br/>Port 3001]
            FS2[Flask Server 2<br/>Port 3002]
            FSN[Flask Server N<br/>Port 300N]
        end
    end
    
    subgraph "Lambda Runtime"
        LR[Local Lambda Runner]
        EC[Environment Config]
        
        subgraph "Docker Containers"
            DC1[Container 1]
            DC2[Container 2]
            DCN[Container N]
        end
    end
    
    HTTP --> PM
    PM --> FUM
    FUM --> FS1
    FUM --> FS2
    FUM --> FSN
    
    FS1 --> LR
    FS2 --> LR
    FSN --> LR
    
    LR --> EC
    EC --> DC1
    EC --> DC2
    EC --> DCN
```

## Request Processing Flow

```mermaid
sequenceDiagram
    participant Client
    participant Flask as Flask Server
    participant Formatter as Event Formatter
    participant Runner as Lambda Runner
    participant Docker as Docker Container
    participant Lambda as Lambda Function
    
    Client->>Flask: HTTP Request
    Flask->>Formatter: Process Request
    Formatter->>Formatter: Convert to Lambda v2.0 Event
    Formatter->>Runner: Invoke with Event
    Runner->>Runner: Load Environment Variables
    Runner->>Docker: Create/Start Container
    Docker->>Lambda: Execute Function
    Lambda-->>Docker: Return Response
    Docker-->>Runner: Container Output
    Runner-->>Formatter: Lambda Response
    Formatter->>Formatter: Format HTTP Response
    Formatter-->>Flask: HTTP Response
    Flask-->>Client: Return Response
```

## Component Relationships

```mermaid
classDiagram
    class LocalCommand {
        +invoke()
        +start_api()
        +start_lambda()
        +start_function_urls()
    }
    
    class FunctionUrlManager {
        -invoke_context
        -host: str
        -port_range: tuple
        -services: dict
        +start_all()
        +start_function()
        +stop_all()
    }
    
    class LocalFunctionUrlService {
        -function_name: str
        -lambda_runner
        -port: int
        -app: Flask
        +start()
        +stop()
        -handle_request()
    }
    
    class PortManager {
        -allocated_ports: set
        -port_range: tuple
        +allocate_port()
        +release_port()
        +is_port_available()
    }
    
    class LocalLambdaRunner {
        -local_runtime
        -function_provider
        -env_vars_values: dict
        +invoke()
        +get_invoke_config()
        -make_env_vars()
    }
    
    class EnvironmentVariables {
        -variables: dict
        -override_values: dict
        -shell_env_values: dict
        +resolve()
        -stringify_value()
    }
    
    class LambdaRuntime {
        -container_manager
        -image_builder
        +create()
        +invoke()
        +run()
    }
    
    LocalCommand --> FunctionUrlManager
    FunctionUrlManager --> LocalFunctionUrlService
    FunctionUrlManager --> PortManager
    LocalFunctionUrlService --> LocalLambdaRunner
    LocalLambdaRunner --> EnvironmentVariables
    LocalLambdaRunner --> LambdaRuntime
```

## Data Flow for Environment Variables

```mermaid
graph TD
    subgraph "Input Sources"
        T[Template Variables]
        J[JSON File<br/>--env-vars]
        S[Shell Environment]
    end
    
    subgraph "Processing"
        EV[EnvironmentVariables Class]
        R[resolve() Method]
        P[Priority Logic]
    end
    
    subgraph "Output"
        D[Docker Container<br/>Environment]
        L[Lambda Function]
    end
    
    T --> EV
    J --> EV
    S --> EV
    
    EV --> R
    R --> P
    
    P -->|1. Override Values<br/>Highest Priority| D
    P -->|2. Shell Values<br/>Medium Priority| D
    P -->|3. Template Values<br/>Lowest Priority| D
    
    D --> L
```

## Testing Architecture

```mermaid
graph TB
    subgraph "Test Suite"
        UT[Unit Tests]
        IT[Integration Tests]
        FT[Functional Tests]
        ET[End-to-End Tests]
    end
    
    subgraph "Test Infrastructure"
        TF[Test Fixtures]
        TD[Test Data]
        TM[Test Mocks]
        TC[Test Containers]
    end
    
    subgraph "Coverage Areas"
        CLI_T[CLI Commands]
        SVC_T[Services]
        RT_T[Runtime]
        DOC_T[Docker Integration]
    end
    
    UT --> TM
    IT --> TF
    IT --> TD
    FT --> TC
    ET --> TC
    
    CLI_T --> UT
    SVC_T --> UT
    SVC_T --> IT
    RT_T --> IT
    DOC_T --> FT
    DOC_T --> ET
```

## Deployment Pipeline

```mermaid
graph LR
    subgraph "Development"
        DEV[Local Development]
        TEST[Run Tests]
        BUILD[Build Package]
    end
    
    subgraph "CI/CD"
        CI[Continuous Integration]
        CD[Continuous Deployment]
        REL[Release Management]
    end
    
    subgraph "Distribution"
        PIP[PyPI Package]
        BREW[Homebrew]
        DOCKER[Docker Images]
        BIN[Binary Releases]
    end
    
    DEV --> TEST
    TEST --> BUILD
    BUILD --> CI
    CI --> CD
    CD --> REL
    
    REL --> PIP
    REL --> BREW
    REL --> DOCKER
    REL --> BIN
```

## Error Handling Flow

```mermaid
flowchart TD
    Start([User Command]) --> Parse{Parse Arguments}
    Parse -->|Invalid| E1[UserException]
    Parse -->|Valid| Init[Initialize Context]
    
    Init --> Check{Check Docker}
    Check -->|Not Available| E2[DockerIsNotReachableException]
    Check -->|Available| Load[Load Template]
    
    Load --> Validate{Validate SAM}
    Validate -->|Invalid| E3[InvalidSamDocumentException]
    Validate -->|Valid| Find[Find Functions]
    
    Find --> HasURLs{Has Function URLs?}
    HasURLs -->|No| E4[NoFunctionUrlsDefined]
    HasURLs -->|Yes| Allocate[Allocate Ports]
    
    Allocate --> StartSvc[Start Services]
    StartSvc --> Running{Service Running?}
    Running -->|Error| E5[Service Start Error]
    Running -->|Success| Wait[Wait for Requests]
    
    Wait --> Handle[Handle Requests]
    Handle --> Response[Return Response]
    
    E1 --> End([Exit with Error])
    E2 --> End
    E3 --> End
    E4 --> End
    E5 --> End
    Response --> Wait
```

---

## Key Architectural Principles

1. **Separation of Concerns**: Each layer has distinct responsibilities
2. **Dependency Inversion**: High-level modules don't depend on low-level modules
3. **Single Responsibility**: Each class/module has one reason to change
4. **Open/Closed Principle**: Open for extension, closed for modification
5. **Interface Segregation**: Clients shouldn't depend on interfaces they don't use

## Benefits of This Architecture

- **Testability**: Each component can be tested in isolation
- **Maintainability**: Clear boundaries between components
- **Scalability**: Easy to add new features without affecting existing code
- **Flexibility**: Components can be replaced or modified independently
- **Reusability**: Common functionality is abstracted and reusable
