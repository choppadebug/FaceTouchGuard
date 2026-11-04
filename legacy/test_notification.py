from windows_toasts import WindowsToaster, Toast

toaster = WindowsToaster("Face Touch Guard")

notification = Toast()
notification.text_fields = [
    "Face Touch Guard",
    "This is your first desktop notification!"
]

toaster.show_toast(notification)

print("Notification submitted.")
