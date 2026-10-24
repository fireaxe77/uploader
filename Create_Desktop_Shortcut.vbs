' Creates a 'Montage Uploader' shortcut on the Desktop. Drop a montage .mp4 onto it.
Set sh = CreateObject("WScript.Shell")
Set fs = CreateObject("Scripting.FileSystemObject")
here = fs.GetParentFolderName(WScript.ScriptFullName)
Set lnk = sh.CreateShortcut(sh.SpecialFolders("Desktop") & "\Montage Uploader.lnk")
lnk.TargetPath = here & "\Montage Uploader.bat"
lnk.WorkingDirectory = here
If fs.FileExists(here & "\icon.ico") Then lnk.IconLocation = here & "\icon.ico"
lnk.WindowStyle = 7
lnk.Save
MsgBox "Shortcut created on the Desktop: drop a montage .mp4 onto it.", 64, "Montage Uploader"
