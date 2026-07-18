# Peridot Sovereign Kernel - Failure State Diagrams
> Engineered by uncoalesced

This document provides visual documentation of how the Peridot kernel intercepts low-level failures through its asynchronous event queue and Finite State Machine (FSM). The diagrams use Mermaid.js syntax for state visualization.

## VRAM Watchdog Panic & Recovery

The VRAM watchdog daemon monitors GPU memory usage and triggers a kernel panic when critical thresholds are exceeded outside of allowed states (INFERENCE or FAH_ACTIVE). This diagram shows the normal flow and the failure divergence.

```mermaid
stateDiagram-v2
    [*] --> BOOT
    BOOT --> IDLE : Boot sequence complete
    
    state IDLE {
        [*] --> Waiting
        Waiting --> FAH_ACTIVE : Research threshold met & research_allowed=true
        FAH_ACTIVE --> IDLE : Research interrupted or disabled
        Waiting --> INTERRUPT_WAIT : Prompt received
    }
    
    INTERRUPT_WAIT --> VRAM_PURGE : Initiate hardware handoff
    VRAM_PURGE --> INFERENCE : Hardware cleared successfully
    INFERENCE --> COOLDOWN : LLM payload complete
    COOLDOWN --> IDLE : Return to standby
    
    %% Failure paths from watchdog
    state "Watchdog Monitor" as Watchdog
    Watchdog : Polls VRAM every 100ms
    Watchdog --> IDLE : Normal operation (VRAM < CRITICAL)
    Watchdog --> PANIC_VRAM : Critical VRAM & not in INFERENCE/FAH_ACTIVE
    
    state PANIC_VRAM {
        [*] --> PanicState
        PanicState --> [*] : Kernel panic triggered
    }
    
    PANIC_VRAM --> [*] : Return 503 error, discard prompt
    [*] --> COOLDOWN : Safe transition via FSM
    COOLDOWN --> IDLE : Reset to standby
    
    %% Alternative panic triggers
    Watchdog --> PANIC_TIMEOUT : FAH hang detected (>2.0s)
    state PANIC_TIMEOUT {
        [*] --> TimeoutPanic
        TimeoutPanic --> [*] : FAH failed to release VRAM
    }
    PANIC_TIMEOUT --> [*] : Return 503 error
    [*] --> COOLDOWN : Safe transition
```

### Key Failure States:
- **PANIC_VRAM**: Triggered when VRAM usage exceeds `CRITICAL_VRAM_MB` (total VRAM - 100MB) while kernel is not in `INFERENCE` or `FAH_ACTIVE` states.
- **PANIC_TIMEOUT**: Triggered when Folding@Home fails to yield VRAM within 2.0-second timeout after pause signal.
- Both panic states transition to `COOLDOWN` via the FSM's `orchestrator_loop`, ensuring safe recovery without OS-level crash.

## Autonomous RAG Degradation

The semantic router in `server.py` monitors NVMe I/O latency during vector retrieval and autonomously adjusts retrieval depth (`top_k`) to prevent bottlenecks. This diagram shows the decision flow.

```mermaid
stateDiagram-v2
    [*] --> IDLE_Router
    state IDLE_Router {
        [*] --> ReceiveQuery
        ReceiveQuery --> EmbedQuery : Generate query vector
        EmbedQuery --> StartTimer : Start precision timer
        StartTimer --> ExecuteSearch : vault.search(query_vector, top_k=current_depth)
        ExecuteSearch --> StopTimer : Stop timer
        StopTimer --> MeasureLatency : latency_ms = elapsed * 1000
        MeasureLatency --> EvaluateThreshold : Compare to RETRIEVAL_LATENCY_THRESHOLD_MS (100ms)
        
        state EvaluateThreshold {
            [*] --> LatencyOK : latency_ms ≤ 100ms
            [*] --> LatencyHIGH : latency_ms > 100ms
        }
        
        LatencyOK --> UpdateDepthOK : Increase depth (recovery)
        LatencyHIGH --> UpdateDepthHIGH : Decrease depth (throttling)
        
        UpdateDepthOK --> ApplyDepth : current_depth = min(current_depth + 0.5, 6)
        UpdateDepthHIGH --> ApplyDepth : current_depth = max(current_depth - 2, 1)
        
        ApplyDepth --> ProcessResults : Process retrieved chunks
        ProcessResults --> [*] : Return context for LLM
        
        %% Depth bounds
        UpdateDepthOK --> DepthMaxCheck : Is current_depth ≥ 6?
        DepthMaxCheck --> YesOK : Yes
        DepthMaxCheck --> NoOK : No
        YesOK --> ApplyDepth : current_depth = 6
        NoOK --> ApplyDepth : Apply normal increase
        
        UpdateDepthHIGH --> DepthMinCheck : Is current_depth ≤ 1?
        DepthMinCheck --> YesHIGH : Yes
        DepthMinCheck --> NoHIGH : No
        YesHIGH --> ApplyDepth : current_depth = 1
        NoHIGH --> ApplyDepth : Apply normal decrease
    }
    
    %% Global depth variable shared across requests
    note right of IDLE_Router
        current_retrieval_depth is a global variable
        initialized to 6 (full depth)
        ranges from 1 to 6
    end
```

### Degradation Behavior:
- **Normal Operation** (latency ≤ 100ms): Gradually increases retrieval depth toward maximum (6) for optimal contextual accuracy.
- **Pressure Response** (latency > 100ms): Rapidly decreases retrieval depth by 2 steps to reduce NVMe I/O load.
- **Bounds**: Depth clamped between 1 and 6 to ensure functional RAG while protecting disk subsystem.
- **Logging**: Each adjustment triggers GhostLogger telemetry for operational visibility.

## Combined Failure & Recovery Flow

This diagram illustrates how both failure mechanisms interact with the overall kernel state machine.

```mermaid
stateDiagram-v2
    [*] --> BOOT
    BOOT --> IDLE : Initialize
    
    state IDLE {
        [*] --> Monitoring
        Monitoring --> FAH_ACTIVE : Research threshold met
        FAH_ACTIVE --> IDLE : Research yields or disabled
        Monitoring --> PromptWait : Awaiting input
    }
    
    PromptWait --> INTERRUPT_WAIT : Prompt received
    INTERRUPT_WAIT --> VRAM_PURGE : Start handoff
    VRAM_PURGE --> INFERENCE : Hardware ready
    INFERENCE --> RAG_EVAL : Semantic routing active
    RAG_EVAL --> COOLDOWN : LLM complete
    COOLDOWN --> IDLE : Reset
    
    %% Failure intersections
    state "VRAM Watchdog" as Watchdog
    Watchdog --> IDLE : Normal (VRAM safe)
    Watchdog --> PANIC : Critical VRAM & not in {INFERENCE, FAH_ACTIVE}
    
    state "RAG Monitor" as RAGMon
    RAGMon --> IDLE_Router : Normal latency
    RAGMon --> ThrottleActive : High latency detected
    
    %% Panic recovery
    PANIC --> COOLDOWN : Safe transition via FSM
    COOLDOWN --> IDLE : Full recovery
    
    %% Throttling recovery
    ThrottleActive --> IDLE_Router : Latency normalized
```

### System Resilience Properties:
1. **Isolation**: Failures in one subsystem (VRAM or I/O) do not crash the entire kernel.
2. **Graceful Degradation**: RAG throttling preserves functionality while reducing load.
3. **Deterministic Recovery**: All failure paths transition through `COOLDOWN` to `IDLE`, ensuring clean state reset.
4. **No Silent Failures**: All events are logged via GhostLogger and telemetry endpoints.