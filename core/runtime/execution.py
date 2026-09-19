    return ExecutionResult(
        status=status,
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        duration_seconds=result.duration_seconds,
        timed_out=result.timed_out,
        stdout_truncated=result.stdout_truncated,
        stderr_truncated=result.stderr_truncated,
        verified=result.verified if verified is None else verified,
        cleanup_completed=(
            result.cleanup_completed
            if cleanup_completed is None
            else cleanup_completed
        ),
    )