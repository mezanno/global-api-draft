"""
Simple tests with Gradio to see how it works with async and sync functions.

Test with the `test_curl.sh` script.
"""

import argparse
import asyncio
import time

import gradio as gr

class Greeter:
    """Worker object with shared state between threads."""
    def __init__(self, delay_s: float):
        self.delay_s = delay_s

    async def async_greet(self, name):
        """Fake work done in async mode."""
        print(f"Received request for {name} will sleep for {self.delay_s}s (async=True).")
        await asyncio.sleep(self.delay_s)
        return f"Hello {name} with {self.delay_s}s of delay (async=True)."

    def sync_greet(self, name):
        """Fake work done in sync mode."""
        print(f"Received request for {name} will sleep for {self.delay_s}s (async=False).")
        time.sleep(self.delay_s)
        return f"Hello {name} with {self.delay_s}s of delay (async=False)."

if __name__ == "__main__":
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Greeter API")
    parser.add_argument("--delay", type=float, default=2.0, help="Delay in seconds")
    parser.add_argument("--async", dest="asynchronous", action="store_true", help="Enable asynchronous mode")
    parser.add_argument("--concurrency_limit", type=int, help="Maximum number of this event that can be running simultaneously", default=1)
    parser.set_defaults(asynchronous=False)
    args = parser.parse_args()

    # Initialize Greeter with command-line arguments
    greeter = Greeter(delay_s=args.delay)
    # Note: it is a bug to use some "async def" function when having some synchronous work inside.
    # This would make FastAPI to switch coroutine context instead of passing heartbeats to the clients.
    greet = greeter.async_greet if args.asynchronous else greeter.sync_greet

    # Create a Gradio interface
    demo = gr.Interface(
        fn=greet,
        inputs=["text"],
        outputs=["text"],
        concurrency_limit=args.concurrency_limit,
    )

    demo.launch()
