"""Signal bot entrypoint — Phase 0 stub.

Real message polling, file uploads, quick-reply buttons, and AI Gateway
integration land in Phase 3, once a Signal phone number is provisioned and
signal-cli registration is complete. For now this just proves the service
boots and can be health-checked.
"""
import time


def main() -> None:
    print("signal-bot: not yet implemented, see apps/signal-bot/README.md (Phase 3)")
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
