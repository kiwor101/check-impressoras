Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
folder = fso.GetParentFolderName(WScript.ScriptFullName)
shell.CurrentDirectory = folder
shell.Run "cmd /c where pythonw >nul 2>nul && start """" pythonw.exe ""check_impressoras_gui.py"" || start """" pyw.exe ""check_impressoras_gui.py""", 0, False
