import random
import time

import optuna
import optuna_distributed

# from dask.distributed import Client
from dask.distributed import Client, SSHCluster


def objective(trial):
    x = trial.suggest_float("x", -100, 100)
    y = trial.suggest_categorical("y", [-1, 0, 1])
    # Some expensive model fit happens here...
    # time.sleep(random.uniform(1.0, 2.0))
    return x**2 + y


if __name__ == "__main__":
    # client = Client("tcp://172.17.0.3:8786")  # Enables distributed optimization.

    cluster = SSHCluster(
        ["localhost", "localhost"],
        # connect_options={"known_hosts": None},
        worker_options={"nthreads": 2, "n_workers": 2},
        scheduler_options={"port": 0, "dashboard_address": ":8797"},
    )
    client = Client(cluster)
    # client = None  # Enables local asynchronous optimization.
    study = optuna_distributed.from_study(optuna.create_study(), client=client)
    study.optimize(objective, n_trials=1000)
    print(study.best_value)


# remote
# docker run -e EXTRA_PIP_PACKAGES="holobench" --network dask ghcr.io/dask/dask dask-worker scheduler:8786 # start worker

# docker run --network dask -p 8787:8787 --name scheduler ghcr.io/dask/dask dask-scheduler  # start scheduler

# docker run -e EXTRA_PIP_PACKAGES="holobench" --network dask ghcr.io/dask/dask dask-worker scheduler:8786 # start worker


# local
# dask scheduler
# then
# dask worker tcp://172.19.0.2:8786 --nworkers 15 --nthreads 1
