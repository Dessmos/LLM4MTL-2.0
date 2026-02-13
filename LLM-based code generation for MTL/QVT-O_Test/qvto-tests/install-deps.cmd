@echo off
REM ============================================================================
REM install-deps.cmd
REM Downloads Eclipse QVT-O, OCL, and LPG JARs from Eclipse p2 update sites,
REM then installs them into the local Maven repository.
REM
REM Usage: install-deps.cmd
REM Then:  mvn clean test
REM ============================================================================

setlocal

set QVTO_BASE=https://download.eclipse.org/mmt/qvto/updates/releases/3.10.8/plugins
set OCL_BASE=https://download.eclipse.org/modeling/mdt/ocl/updates/releases/6.19.0/plugins
set LIB=lib

if not exist "%LIB%" mkdir "%LIB%"

echo ============================================================
echo Step 1: Downloading JARs from Eclipse update sites...
echo ============================================================

REM --- QVT-O JARs (from MMT QVT-O 3.10.8) ---
echo Downloading QVT-O core...
curl -# -L -o "%LIB%\org.eclipse.m2m.qvt.oml.jar" "%QVTO_BASE%/org.eclipse.m2m.qvt.oml_3.10.8.v20231126-0839.jar"

echo Downloading QVT-O common...
curl -# -L -o "%LIB%\org.eclipse.m2m.qvt.oml.common.jar" "%QVTO_BASE%/org.eclipse.m2m.qvt.oml.common_3.10.2.v20231126-0839.jar"

echo Downloading QVT-O CST parser...
curl -# -L -o "%LIB%\org.eclipse.m2m.qvt.oml.cst.parser.jar" "%QVTO_BASE%/org.eclipse.m2m.qvt.oml.cst.parser_3.9.0.v20231126-0839.jar"

echo Downloading QVT-O EMF util...
curl -# -L -o "%LIB%\org.eclipse.m2m.qvt.oml.emf.util.jar" "%QVTO_BASE%/org.eclipse.m2m.qvt.oml.emf.util_3.10.6.v20231126-0839.jar"

echo Downloading QVT-O Ecore ImperativeOCL...
curl -# -L -o "%LIB%\org.eclipse.m2m.qvt.oml.ecore.imperativeocl.jar" "%QVTO_BASE%/org.eclipse.m2m.qvt.oml.ecore.imperativeocl_3.10.2.v20231126-0839.jar"

echo Downloading QVT-O runtime...
curl -# -L -o "%LIB%\org.eclipse.m2m.qvt.oml.runtime.jar" "%QVTO_BASE%/org.eclipse.m2m.qvt.oml.runtime_3.10.7.v20231126-0839.jar"

echo Downloading QVT-O OCL bridge...
curl -# -L -o "%LIB%\org.eclipse.m2m.qvt.oml.ocl.jar" "%QVTO_BASE%/org.eclipse.m2m.qvt.oml.ocl_3.10.2.v20231126-0839.jar"

REM --- OCL JARs (from MDT OCL 6.19.0) ---
echo Downloading OCL core...
curl -# -L -o "%LIB%\org.eclipse.ocl.jar" "%OCL_BASE%/org.eclipse.ocl_3.19.0.v20231129-1236.jar"

echo Downloading OCL Ecore...
curl -# -L -o "%LIB%\org.eclipse.ocl.ecore.jar" "%OCL_BASE%/org.eclipse.ocl.ecore_3.19.0.v20231129-1236.jar"

echo Downloading OCL common...
curl -# -L -o "%LIB%\org.eclipse.ocl.common.jar" "%OCL_BASE%/org.eclipse.ocl.common_1.19.0.v20231129-1236.jar"

echo.
echo ============================================================
echo Step 2: Installing JARs to local Maven repository...
echo ============================================================

REM --- QVT-O ---
call mvn install:install-file -DgroupId=org.eclipse.m2m -DartifactId=org.eclipse.m2m.qvt.oml -Dversion=3.10.8 -Dpackaging=jar -Dfile="%LIB%\org.eclipse.m2m.qvt.oml.jar" -q
if errorlevel 1 (echo FAILED: org.eclipse.m2m.qvt.oml) else (echo   Installed org.eclipse.m2m.qvt.oml 3.10.8)

call mvn install:install-file -DgroupId=org.eclipse.m2m -DartifactId=org.eclipse.m2m.qvt.oml.common -Dversion=3.10.2 -Dpackaging=jar -Dfile="%LIB%\org.eclipse.m2m.qvt.oml.common.jar" -q
if errorlevel 1 (echo FAILED: org.eclipse.m2m.qvt.oml.common) else (echo   Installed org.eclipse.m2m.qvt.oml.common 3.10.2)

call mvn install:install-file -DgroupId=org.eclipse.m2m -DartifactId=org.eclipse.m2m.qvt.oml.cst.parser -Dversion=3.9.0 -Dpackaging=jar -Dfile="%LIB%\org.eclipse.m2m.qvt.oml.cst.parser.jar" -q
if errorlevel 1 (echo FAILED: org.eclipse.m2m.qvt.oml.cst.parser) else (echo   Installed org.eclipse.m2m.qvt.oml.cst.parser 3.9.0)

call mvn install:install-file -DgroupId=org.eclipse.m2m -DartifactId=org.eclipse.m2m.qvt.oml.emf.util -Dversion=3.10.6 -Dpackaging=jar -Dfile="%LIB%\org.eclipse.m2m.qvt.oml.emf.util.jar" -q
if errorlevel 1 (echo FAILED: org.eclipse.m2m.qvt.oml.emf.util) else (echo   Installed org.eclipse.m2m.qvt.oml.emf.util 3.10.6)

call mvn install:install-file -DgroupId=org.eclipse.m2m -DartifactId=org.eclipse.m2m.qvt.oml.ecore.imperativeocl -Dversion=3.10.2 -Dpackaging=jar -Dfile="%LIB%\org.eclipse.m2m.qvt.oml.ecore.imperativeocl.jar" -q
if errorlevel 1 (echo FAILED: org.eclipse.m2m.qvt.oml.ecore.imperativeocl) else (echo   Installed org.eclipse.m2m.qvt.oml.ecore.imperativeocl 3.10.2)

call mvn install:install-file -DgroupId=org.eclipse.m2m -DartifactId=org.eclipse.m2m.qvt.oml.runtime -Dversion=3.10.7 -Dpackaging=jar -Dfile="%LIB%\org.eclipse.m2m.qvt.oml.runtime.jar" -q
if errorlevel 1 (echo FAILED: org.eclipse.m2m.qvt.oml.runtime) else (echo   Installed org.eclipse.m2m.qvt.oml.runtime 3.10.7)

call mvn install:install-file -DgroupId=org.eclipse.m2m -DartifactId=org.eclipse.m2m.qvt.oml.ocl -Dversion=3.10.2 -Dpackaging=jar -Dfile="%LIB%\org.eclipse.m2m.qvt.oml.ocl.jar" -q
if errorlevel 1 (echo FAILED: org.eclipse.m2m.qvt.oml.ocl) else (echo   Installed org.eclipse.m2m.qvt.oml.ocl 3.10.2)

REM --- OCL ---
call mvn install:install-file -DgroupId=org.eclipse.ocl -DartifactId=org.eclipse.ocl -Dversion=3.19.0 -Dpackaging=jar -Dfile="%LIB%\org.eclipse.ocl.jar" -q
if errorlevel 1 (echo FAILED: org.eclipse.ocl) else (echo   Installed org.eclipse.ocl 3.19.0)

call mvn install:install-file -DgroupId=org.eclipse.ocl -DartifactId=org.eclipse.ocl.ecore -Dversion=3.19.0 -Dpackaging=jar -Dfile="%LIB%\org.eclipse.ocl.ecore.jar" -q
if errorlevel 1 (echo FAILED: org.eclipse.ocl.ecore) else (echo   Installed org.eclipse.ocl.ecore 3.19.0)

call mvn install:install-file -DgroupId=org.eclipse.ocl -DartifactId=org.eclipse.ocl.common -Dversion=1.19.0 -Dpackaging=jar -Dfile="%LIB%\org.eclipse.ocl.common.jar" -q
if errorlevel 1 (echo FAILED: org.eclipse.ocl.common) else (echo   Installed org.eclipse.ocl.common 1.19.0)

echo.
echo ============================================================
echo Done! Now run: mvn clean test
echo ============================================================
endlocal
