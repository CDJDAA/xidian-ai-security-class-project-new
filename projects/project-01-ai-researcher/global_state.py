# global_state.py
import queue

LOG_PATH = ""
PROGRESS_QUEUE = queue.Queue()


def report_progress(progress: int, stage: str, detail: str = "") -> None:
    PROGRESS_QUEUE.put({
        "progress": max(0, min(100, int(progress))),
        "stage": stage,
        "detail": detail,
    })

START_FLAG = False
FIRST_MAIN = False


EXIT_FLAG = False
INIT_FLAG = False
# WORKFLOW_FLAG = False
# AGENTCREATE_FLAS = False

# AGENT_CREATOR_AGENT_STATE = False
# META_AGENT_LAST_QUERY = ''
# WORKFLOW_CREATOR_AGENT_STATE = False
# WORKFLOW_AGENT_LAST_QUERY = ''

# container_name = 'auto_agent'
# port = 12345
# test_pull_name = 'autoagent_mirror'
# git_clone = True
# local_env = False