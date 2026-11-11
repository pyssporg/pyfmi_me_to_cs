# Context View

## External Actors

```
┌─────────────────────────────────────────────────────────────────┐
│                      cs-fmu-packager                            │
│                                                                 │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────────┐  │
│  │          │   │          │   │          │   │              │  │
│  │    CLI   │──>│  Spec    │──>│  Mapper  │──>│  Codegen     │  │
│  │    Parser│   │ Validator│   │          │   │  (C + CMake) │  │
│  │          │   │          │   │          │   │              │  │
│  └──────────┘   └──────────┘   └──────────┘   └──────┬───────┘  │
│                                                      │          │
│                                                      ▼          │
│                                              ┌──────────────┐   │
│                                              │              │   │
│                                              │    Builder   │   │
│                                              │  (CMake+ GCC)│   │
│                                              │              │   │
│                                              └──────┬───────┘   │
│                                                     │           │
│                                                     ▼           │
│                                              ┌──────────────┐   │
│                                              │              │   │
│                                              │   Packager   │   │
│                                              │  (FMU ZIP)   │   │
│                                              │              │   │
│                                              └──────────────┘   │
└─────────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
   ┌──────────┐       ┌──────────────┐     ┌──────────────┐
   │   CLI    │       │ FMI Master   │     │ Build Tools  │
   │   User   │       │ Algorithm    │     │ (CMake, GCC, │
   │          │       │ (consumes    │     │  vcpkg)      │
   │          │       │  generated   │     │              │
   │          │       │  FMU)        │     │              │
   └──────────┘       └──────────────┘     └──────────────┘
```

## External Actors

| Actor | Description | Interaction |
| --- | --- | --- |
| CLI User | A person or automated script running `cs-fmu-packager` from the command line. | Provides spec file path and options; receives FMU and build report. |
| FMI Master Algorithm | External co-simulation orchestrator that loads the generated FMU and calls `fmi2DoStep`. | Consumes the packaged Co-Simulation FMU at runtime. |
| Build Tools | System tools: CMake, GCC/Clang, vcpkg. | Used during packaging to compile the generated C wrapper code. Not needed at FMU runtime. |
| Input FMU Files (File System) | FMI 2.0 Model Exchange FMU files on disk. | Read during FMU inspection phase; embedded in generated FMU. |