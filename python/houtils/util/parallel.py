import importlib
import inspect
import os
import pickle
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any, Callable


class Parallel:
    def __init__(
        self,
        function: Callable[..., object],
        *args: Any | Sequence[Any] | Sequence[Sequence[Any]],
    ):
        self.function = function
        self.module_path = self.get_module_path()
        self.function_name = function.__name__

        self.store_args = args
        self.args = self.process_args()

        self.tempfile_path = None
        self.process = None

    def get_module_path(self) -> str:
        module = inspect.getmodule(self.function)
        if module:
            return module.__name__
        raise ImportError(f"Cannot determine module for function {self.function_name}")

    def process_args(self) -> list[tuple[Any, ...]]:
        function_signature = inspect.signature(self.function)
        required_num_args = sum(
            param.default == inspect.Parameter.empty
            and param.kind
            in {
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            }
            for param in function_signature.parameters.values()
        )

        args = self.store_args

        if (
            len(args) == 1
            and isinstance(args[0], (list, tuple))
            and all(isinstance(item, (list, tuple)) for item in args[0])
        ):
            chunks = [tuple(item) for item in args[0]]

        elif (
            len(args) == 1
            and isinstance(args[0], (list, tuple))
            and not isinstance(args[0], (str, bytes))
        ):
            seq = list(args[0])

            if len(seq) == required_num_args:
                chunks = [tuple(seq)]
            else:
                chunks = [
                    tuple(seq[i : i + required_num_args])
                    for i in range(0, len(seq), required_num_args)
                ]

        else:
            chunks = [
                tuple(args[i : i + required_num_args])
                for i in range(0, len(args), required_num_args)
            ]

        # Validate all chunks
        for chunk in chunks:
            try:
                function_signature.bind(*chunk)
            except TypeError as e:
                raise ValueError(f"Argument mismatch in chunk {chunk}: {e}")

        return chunks

    def execute(
        self,
        interpreter: Path | str | None = None,
        force_temp_file: bool = False,
    ) -> "Parallel":

        # Setup env
        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join(sys.path)

        # Get the current file path to run when main
        script_path = str(__file__)
        if not script_path.endswith(".py"):
            script_path += ".py"

        # Format args
        if not force_temp_file and not os.name == "nt":
            args_to_pass = self.args
        else:
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                pickle.dump(self.args, temp_file)
                self.tempfile_path = temp_file.name
            args_to_pass = self.tempfile_path

        # Send Args
        self.process = subprocess.Popen(
            (
                str(interpreter or sys.executable),
                script_path,
            ),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        self.process.communicate(
            pickle.dumps((self.module_path, self.function_name, args_to_pass))
        )

        return self

    def retrieve(self, timeout: float = 0) -> Any:
        if not self.process:
            return None

        try:
            stdout, stderr = self.process.communicate(
                timeout=timeout if timeout != 0 else None
            )
        except subprocess.TimeoutExpired:
            self.process.kill()
            raise TimeoutError("Subprocess timed out")
        finally:
            if self.tempfile_path:
                os.unlink(self.tempfile_path)
                self.tempfile_path = None

        if errors := (pickle.loads(stderr) if stderr else None):
            raise RuntimeError(errors)
        else:
            flat_results = pickle.loads(stdout)
            if len(self.store_args) == 1 and isinstance(
                self.store_args[0], (list, tuple)
            ):
                return [flat_results[idx] for idx in range(len(flat_results))]
            return flat_results


def result(arg: Any):
    sys.stdout.buffer.write(pickle.dumps(arg))
    sys.stdout.buffer.flush()
    sys.exit(0)


def error(arg: Any):
    sys.stderr.buffer.write(pickle.dumps(f"ERROR: {arg}"))
    sys.stderr.buffer.flush()
    sys.exit(1)


if __name__ == "__main__":
    data = pickle.loads(sys.stdin.buffer.read())
    if len(data) != 3:
        error("Incorrect arguments passed to subprocess")

    module_path, function_name, arg = data

    # Load Module
    try:
        module = importlib.import_module(module_path)
    except ImportError as e:
        error(f"Failed to import module {module_path}: {e}")

    # Get Function
    try:
        function = getattr(
            module, function_name  # pyright: ignore[reportPossiblyUnboundVariable]
        )
    except AttributeError:
        error(f"Function {function_name} not found in module {module_path}")

    # Load args
    if isinstance(arg, str) and Path(arg).exists():
        try:
            with open(arg, "rb") as temp_file:
                args = pickle.load(temp_file)
        except FileNotFoundError as e:
            error(f"Failed to load arguments from temp file: {e}")
    else:
        args = arg

    # Execute
    with ProcessPoolExecutor() as executor:
        futures = {
            executor.submit(function, *chunk): idx for idx, chunk in enumerate(args)  # type: ignore[arg-type]
        }
        results = {}
        for future, idx in futures.items():
            try:
                results[idx] = future.result()
            except Exception as e:
                results[idx] = f"ERROR: {e}"

    result(results)
