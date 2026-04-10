from queue import Full, Empty


def put_latest(q, item):
    try:
        q.put_nowait(item)
        return
    except Full:
        try:
            q.get_nowait()
        except Empty:
            pass
        try:
            q.put_nowait(item)
        except Full:
            pass