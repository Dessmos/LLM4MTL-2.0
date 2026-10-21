@echo off
REM Batch-Skrict to delete target-folder

for %%D in (
    "consistency\target"
    "model\target"
    "viewtype\target"
    "vsum\target"
) do (
    if exist %%D (
        echo Delete %%D ...
        rmdir /S /Q %%D
    ) else (
        echo %%D 
    )
)


