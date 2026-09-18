---
name: pruebas-locales-servidor
description: Reglas para levantar y probar backend (Django, :8000) y frontend (NiceGUI, :8080) de este proyecto en local sin acumular procesos huérfanos. USAR SIEMPRE antes de arrancar el sistema para depurar o probar algo manualmente, y OBLIGATORIO al terminar esa prueba (matar procesos y borrar archivos temporales, sin excepción).
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

3. **Terminada la prueba, cerrar y eliminar de inmediato — nunca dejarlo
   corriendo "por si acaso".** Esto es obligatorio, no opcional, y va al final
   de CADA sesión de prueba, no solo cuando algo salió mal. Checklist mínimo:

   a. Matar backend y frontend (y sus hijos de recarga, ver regla 2):
      ```powershell
      Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
          Where-Object { $_.CommandLine -like "*manage.py*" -or $_.CommandLine -like "*frontend*main.py*" } |
          ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
      ```
   b. Confirmar con `Get-NetTCPConnection -LocalPort 8080,8000` que no queda
      ningún `Listen` (solo `TimeWait`/`FinWait2` es aceptable, se cierran solos).
   c. **Cerrar el navegador de Playwright** con `mcp__playwright__browser_close`
      si se usó para verificar. Es una ventana de Chrome real y visible en la
      pantalla de Nicolás: si no se cierra, se queda ahí mostrando la página
      vieja y termina con "Connection lost" cuando se matan los servidores,
      pareciendo que quedó un servidor corriendo. Matar los procesos de Python
      NO cierra esta ventana.
   d. Borrar los archivos y carpetas que la prueba haya generado y que no sean
      parte del proyecto: logs (`*.log`, `*.err`), bases de datos desechables
      (`db-*.sqlite3`), capturas y snapshots de Playwright (`.playwright-mcp/`).
   e. Correr `git status` y confirmar árbol de trabajo limpio (o solo con los
      cambios de código que sí correspondía hacer).

   Si se necesita repetir la prueba pronto, mejor usar puertos distintos a los
   de desarrollo normal (como hace `scripts/verificar.ps1`, que usa `8901` para
   el backend y `8902` para la interfaz vía `FRONTEND_PORT`) en vez de
   reutilizar el mismo puerto sin confirmar que quedó libre.

   **El 8080 también es el puerto de Jenkins.** Si Docker Desktop está abierto,
   el contenedor `jenkins` (de `C:\dev\projects\jenkins`) se autoarranca y
   publica el 8080; NiceGUI no puede escuchar ahí y la verificación falla sin
   que el log del frontend diga nada. Comprobar el puerto con
   `Get-NetTCPConnection`, no con una petición HTTP: Jenkins contesta 403 y una
   petición fallida daría el puerto por libre.

   **Para matar procesos, usar el árbol completo.** El proceso que sirve la
   interfaz es un hijo (`multiprocessing.spawn`) que hereda el socket: matar
   solo al padre lo deja huérfano y escuchando. Un filtro WQL por
   `ParentProcessId` devuelve vacío de forma intermitente en este equipo (igual
   que por `ProcessId`), y `taskkill /T` lo bloquea el entorno de Claude Code.
   Lo que funciona: enumerar `Get-CimInstance Win32_Process` sin filtro y
   recorrer los descendientes en PowerShell, como hace `Detener-Arbol` en
   `scripts/verificar.ps1`.

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
