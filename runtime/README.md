# Embedded Runtime

This directory holds project-local runtimes used to reduce external machine dependencies.

## Pellet Java Runtime

- Runtime: Eclipse Temurin JRE 25.0.2+10
- Platform: Windows x64
- Installed path: `runtime/jre/temurin-25.0.2+10-win-x64`
- Official asset: `OpenJDK25U-jre_x64_windows_hotspot_25.0.2_10.zip`

The runtime is pinned because the current `owlready2` Pellet bundle includes
`org/apache/jena/riot/lang/LangRDFXML.class` compiled with class file version `69`,
which requires Java 25.

Resolution order in code:

1. `PELLET_JAVA_EXE`
2. `runtime/jre`
3. `PELLET_JAVA_HOME` / `JAVA_HOME`
4. system `PATH`

If this runtime is updated, re-run the Pellet smoke check and the full pytest suite.
