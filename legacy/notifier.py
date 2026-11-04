from windows_toasts import WindowsToaster, Toast


class TouchNotifier:
    def __init__(self, cooldown_seconds=8.0):
        self.toaster = WindowsToaster("Face Touch Guard")

        self.cooldown_seconds = cooldown_seconds
        self.last_notification = float("-inf")

    def notify(self, event_count, now):
        """
        Display a notification, unless we're in cooldown.

        Returns True if the notification was submitted.
        """

        # Prevent excessive notifications.
        if now - self.last_notification < self.cooldown_seconds:
            return False

        toast = Toast()
        toast.text_fields = [
            "Face Touch Guard",
            f"Possible face touch detected! "
            f"Total events: {event_count}"
        ]

        try:
            self.toaster.show_toast(toast)
        except Exception as exc:
            print(f"Notification error: {exc}")
            return False

        self.last_notification = now
        return True
