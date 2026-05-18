# Runtime Scheduler Architecture

## Objetivo
Descripción del sistema, sus módulos y flujo de datos.

## Módulos
- Context Builder
- Observability
- Runtime Flow
- Runtime State
- Runtime Adapter
- Runtime Dependencies

## Flujo
1. Scheduler tick inicia
2. Carga estado runtime
3. Ejecuta flujos legacy y auto-pick
4. Captura observaciones y shadow tick
5. Genera tick details
6. Construye runtime flow result
7. Persiste observabilidad y estado runtime
8. Maneja errores y excepciones
...
