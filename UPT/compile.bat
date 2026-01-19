@echo off
REM ============================================================================
REM Script de Compilacion DEFINITIVO - AIEvaluator
REM config.json queda EXTERNO y EDITABLE
REM ============================================================================

echo.
echo ============================================================================
echo   COMPILACION DE AIEvaluator - Config Externo y Editable
echo ============================================================================
echo.

REM ============================================================================
REM PASO 1: VERIFICAR ARCHIVOS NECESARIOS
REM ============================================================================

echo [1/5] Verificando archivos Python necesarios...
echo.

set MISSING=0

if not exist "main_dual_poller.py" (
    echo ERROR: Falta main_dual_poller.py
    set MISSING=1
)

if not exist "token_manager.py" (
    echo ERROR: Falta token_manager.py
    set MISSING=1
)

if not exist "recovery_system.py" (
    echo ERROR: Falta recovery_system.py
    set MISSING=1
)

if not exist "log.py" (
    echo ERROR: Falta log.py
    set MISSING=1
)

if not exist "connection_settings.py" (
    echo ERROR: Falta connection_settings.py
    set MISSING=1
)

if not exist "signals_handler.py" (
    echo ERROR: Falta signals_handler.py
    set MISSING=1
)

if not exist "debug_mode.py" (
    echo ERROR: Falta debug_mode.py
    set MISSING=1
)

if not exist "dual_poller_system.py" (
    echo ERROR: Falta dual_poller_system.py
    set MISSING=1
)

if not exist "audio_process.py" (
    echo ERROR: Falta audio_process.py
    set MISSING=1
)

if not exist "analysis.py" (
    echo ERROR: Falta analysis.py
    set MISSING=1
)

if not exist "transcripcion.py" (
    echo ERROR: Falta transcripcion.py
    set MISSING=1
)

if not exist "sql_connection.py" (
    echo ERROR: Falta sql_connection.py
    set MISSING=1
)

if not exist "config.json" (
    echo ERROR: Falta config.json
    set MISSING=1
)

if %MISSING%==1 (
    echo.
    echo ============================================================================
    echo   ERROR: FALTAN ARCHIVOS CRITICOS
    echo ============================================================================
    echo.
    pause
    exit /b 1
)

echo Todos los archivos Python presentes: OK
echo.

REM ============================================================================
REM PASO 2: VERIFICAR PYINSTALLER
REM ============================================================================

echo [2/5] Verificando PyInstaller...
echo.

python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo PyInstaller no encontrado. Instalando...
    pip install pyinstaller
    if errorlevel 1 (
        echo ERROR: No se pudo instalar PyInstaller
        pause
        exit /b 1
    )
)

echo PyInstaller: OK
echo.

REM ============================================================================
REM PASO 3: LIMPIAR COMPILACIONES ANTERIORES
REM ============================================================================

echo [3/5] Limpiando compilaciones anteriores...
echo.

if exist "build" (
    rmdir /s /q build
    echo - Carpeta build eliminada
)

if exist "dist" (
    rmdir /s /q dist
    echo - Carpeta dist eliminada
)

if exist "__pycache__" (
    rmdir /s /q __pycache__
    echo - Carpeta __pycache__ eliminada
)

echo Limpieza completada
echo.

REM ============================================================================
REM PASO 4: COMPILAR CON PYINSTALLER
REM ============================================================================

echo [4/5] Compilando con PyInstaller...
echo.
echo IMPORTANTE: config.json NO se incluira en el EXE
echo            Quedara EXTERNO para ser editable
echo.
echo NOTA: Esto puede tomar varios minutos...
echo.

REM Comando de compilacion con TODOS los modulos
REM config.json NO se incluye - quedara externo
pyinstaller --onefile ^
    --name="AIEvaluator" ^
    --hidden-import=token_manager ^
    --hidden-import=recovery_system ^
    --hidden-import=log ^
    --hidden-import=connection_settings ^
    --hidden-import=signals_handler ^
    --hidden-import=debug_mode ^
    --hidden-import=dual_poller_system ^
    --hidden-import=audio_process ^
    --hidden-import=analysis ^
    --hidden-import=transcripcion ^
    --hidden-import=sql_connection ^
    --hidden-import=anthropic ^
    --hidden-import=google.generativeai ^
    --hidden-import=pyodbc ^
    --hidden-import=speech_recognition ^
    --hidden-import=pydub ^
    --console ^
    main_dual_poller.py

if errorlevel 1 (
    echo.
    echo ============================================================================
    echo   ERROR: LA COMPILACION FALLO
    echo ============================================================================
    echo.
    pause
    exit /b 1
)

echo.
echo Compilacion exitosa
echo.

REM ============================================================================
REM PASO 5: PREPARAR CARPETA DE DISTRIBUCION
REM ============================================================================

echo [5/5] Preparando carpeta de distribucion...
echo.

REM Verificar que el ejecutable se creo
if not exist "dist\AIEvaluator.exe" (
    echo ERROR: No se genero el ejecutable AIEvaluator.exe
    pause
    exit /b 1
)

echo Ejecutable generado: OK
echo.

REM CRITICO: Copiar config.json EXTERNAMENTE
echo Copiando config.json (EXTERNO - EDITABLE)...
copy "config.json" "dist\" >nul
if errorlevel 1 (
    echo ERROR: No se pudo copiar config.json
    pause
    exit /b 1
) else (
    echo - config.json copiado y EDITABLE
)

REM Crear carpeta de logs
if not exist "dist\logs" mkdir "dist\logs"
echo - Carpeta logs\ creada

REM Copiar scripts SQL (si existen)
if exist "sql_setup.sql" (
    if not exist "dist\sql_scripts" mkdir "dist\sql_scripts"
    copy "sql_setup.sql" "dist\sql_scripts\" >nul
    echo - sql_setup.sql copiado
)

if exist "sql_table.sql" (
    if not exist "dist\sql_scripts" mkdir "dist\sql_scripts"
    copy "sql_table.sql" "dist\sql_scripts\" >nul
    echo - sql_table.sql copiado
)

echo.

REM Crear README
(
echo ============================================================================
echo   AIEvaluator - Sistema de Transcripcion y Analisis con IA
echo ============================================================================
echo.
echo ARCHIVOS INCLUIDOS:
echo   - AIEvaluator.exe    : Ejecutable principal
echo   - config.json        : Configuracion EDITABLE ^(EXTERNO^)
echo   - logs/              : Carpeta de logs
echo.
echo CONFIGURACION:
echo   1. Editar config.json con Notepad o cualquier editor:
echo      notepad config.json
echo.
echo   2. Configurar:
echo      - api_key de Claude o Gemini
echo      - db_connection con tu cadena de conexion SQL Server
echo      - Intervalos de polling si lo deseas
echo.
echo   3. Guardar cambios y ejecutar:
echo      AIEvaluator.exe
echo.
echo INSTALAR COMO SERVICIO:
echo   Descargar NSSM: https://nssm.cc/download
echo.
echo   nssm install AIEvaluator "%%CD%%\AIEvaluator.exe"
echo   nssm set AIEvaluator AppDirectory "%%CD%%"
echo   nssm start AIEvaluator
echo.
echo EDITAR CONFIGURACION EN PRODUCCION:
echo   1. Detener servicio: nssm stop AIEvaluator
echo   2. Editar: notepad config.json
echo   3. Reiniciar: nssm start AIEvaluator
echo.
echo ============================================================================
) > "dist\README.txt"

echo - README.txt creado
echo.

REM ============================================================================
REM RESUMEN FINAL
REM ============================================================================

echo ============================================================================
echo   COMPILACION COMPLETADA EXITOSAMENTE
echo ============================================================================
echo.
echo Archivos generados en: dist\
echo.
dir /b dist
echo.
echo Tamaño del ejecutable:
for %%I in (dist\AIEvaluator.exe) do echo   %%~zI bytes ^(%%~nI.exe^)
echo.
echo ============================================================================
echo   VERIFICACION IMPORTANTE
echo ============================================================================
echo.
echo config.json esta FUERA del EXE y es EDITABLE:
echo   - Para editar: notepad dist\config.json
echo   - Los cambios se aplican al reiniciar AIEvaluator.exe
echo   - NO necesitas recompilar para cambiar configuracion
echo.
echo ============================================================================
echo   SIGUIENTES PASOS
echo ============================================================================
echo.
echo 1. Editar dist\config.json con tus credenciales
echo 2. Probar manualmente:
echo    cd dist
echo    AIEvaluator.exe
echo.
echo 3. Verificar logs:
echo    type dist\logs\ai_evaluator.log
echo.
echo 4. Si funciona OK, instalar como servicio con NSSM
echo.
echo ============================================================================

pause