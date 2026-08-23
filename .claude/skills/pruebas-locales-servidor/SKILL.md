---
name: pruebas-locales-servidor
description: Reglas para levantar y probar backend (Django, :8000) y frontend (NiceGUI, :8080) de este proyecto en local sin acumular procesos huérfanos. USAR SIEMPRE antes de arrancar el sistema para depurar o probar algo manualmente, y al terminar esa prueba.
---

# Pruebas locales de backend/frontend en este proyecto

## Por qué existe esta skill

El 21 de agosto de 2026, una sesión de depuración de "no se conecta con la API al
ingresar las credenciales" se fue por varias horas de callejón sin salida porque
cada reinicio de prueba dejaba el proceso anterior vivo en vez de reemplazarlo.
Al final había **8 instancias de NiceGUI** compitiendo por el puerto 8080
simultáneamente: el navegador hablaba con una al azar (normalmente la más vieja,
sin backend detrás), mientras yo depuraba y reiniciaba otra completamente distinta.
Ningún cambio de código parecía tener efecto porque, en efecto, no lo tenía: el
proceso que respondía nunca era el que yo acababa de editar.

Causa técnica adicional que agravó el problema: en este equipo,
`Get-CimInstance Win32_Process -Filter "ProcessId=$pid"` (consulta por PID exacto)
devuelve vacío de forma intermitente aunque el proceso siga vivo — es una rareza de
WMI, no ausencia real del proceso. `Get-CimInstance Win32_Process -Filter
"Name='python.exe'"` (sin filtrar por PID) sí lo lista siempre. Por eso los
intentos de "matar el proceso X" fallaban en silencio: la consulta no encontraba
nada, se reportaba como limpio, y el proceso seguía vivo y sirviendo tráfico.

## Reglas

1. **Antes de levantar backend/frontend para probar algo, verificar que el puerto
   esté libre**, no asumirlo:
   ```powershell
   Get-NetTCPConnection -LocalPort 8080,8000 -ErrorAction SilentlyContinue |
       Select-Object LocalPort, State, OwningProcess
   ```
   `Get-NetTCPConnection` es la fuente de verdad de qué proceso tiene el puerto
   — más confiable que enumerar procesos por nombre o PID.

2. **Para detener procesos de este proyecto, filtrar por `Name='python.exe'` y
   luego por `CommandLine`, nunca por `ProcessId` directo**:
   ```powershell
   Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
       Where-Object { $_.CommandLine -like "*manage.py*" -or $_.CommandLine -like "*frontend*main.py*" } |
       ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
   ```
   Repetir la consulta después y confirmar `Get-NetTCPConnection` en limpio antes
   de dar por muerto el proceso. Un `Stop-Process` sobre el padre no mata al hijo
   que NiceGUI/Django lanzan por recarga automática: matar también ese hijo
   (aparece como `pythoncore-...\python.exe` con `multiprocessing.spawn`,
   `parent_pid=<pid del padre>` en su `CommandLine`).

3. **Terminada la prueba, matar los procesos de inmediato** (no dejarlos
   corriendo "por si acaso"). Si se necesita repetir la prueba pronto, mejor usar
   puertos distintos a los de desarrollo normal (como hace
   `scripts/verificar.ps1`, que usa `8901` para el backend en vez de `8000`)
   en vez de reutilizar el mismo puerto sin confirmar que quedó libre.

4. **Nunca usar `nohup ... &` de Bash para levantar backend/frontend cuando la
   verificación final la hace un navegador real (Playwright u otro).** El
   entorno de Bash puede correr en un espacio de red aislado del entorno de
   escritorio real; un proceso lanzado ahí puede responder perfectamente a
   `curl` desde el mismo Bash y aun así ser invisible/inalcanzable para el
   navegador real. Para reproducir un bug que el usuario ve en su navegador,
   levantar los procesos con la herramienta que opera sobre el entorno real
   (PowerShell) y verificar con esa misma vía antes de sospechar del código.

5. Si después de todo esto el puerto 8080 sigue atascado, usar
   `mcp__nice-vibes__kill_port_8080` (pide confirmación al usuario antes de
   invocarla) en vez de seguir cazando el proceso manualmente.
