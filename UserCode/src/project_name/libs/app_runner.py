"""
AppRunner orchestrates the application lifecycle:
    setup() → start() → shutdown()

Add your application-specific logic by overriding or extending each phase.
"""


class AppRunner:
    def __init__(self) -> None:
        # TODO: accept and store constructor arguments
        # e.g. self.input_path = input_path
        pass

    def setup(self) -> None:
        """Initialize resources: load config, validate inputs, prepare dependencies."""
        print("Setting up...")

    def start(self) -> None:
        """Run the main application logic."""
        print("Starting app...")

    def shutdown(self) -> None:
        """Release resources and perform cleanup."""
        print("Shutting down...")

    def run(self) -> None:
        """Execute the full application lifecycle."""
        self.setup()
        self.start()
        self.shutdown()
