import sys

def show_progress(current, total, message="Processing", bar_length=30):
    percent = current / total
    filled_length = int(bar_length * percent)
    bar = "█" * filled_length + "░" * (bar_length - filled_length)
    sys.stdout.write(f"\r{message}: [{bar}] {percent:.0%} ({current:,}/{total:,})")
    sys.stdout.flush()