"""Training endpoints. Manual triggers for base retrain and SGD reset."""

from fastapi import APIRouter, BackgroundTasks

router = APIRouter()


@router.post("/base")
def trigger_base_retrain(background: BackgroundTasks) -> dict:
    from app.train.train_base import run as run_train
    background.add_task(run_train)
    return {"status": "queued"}


@router.post("/sgd/reset")
def reset_sgd() -> dict:
    from app.train.init_sgd import run as run_init
    run_init()
    return {"status": "ok"}
