from dishka.entities.scope import BaseScope, new_scope


class AG2Scope(BaseScope):
    RUNTIME = new_scope("RUNTIME", skip=True)
    APP = new_scope("APP")
    CONVERSATION = new_scope("CONVERSATION", skip=True)
    SESSION = new_scope("SESSION", skip=True)
    REQUEST = new_scope("REQUEST")
    ACTION = new_scope("ACTION")
    STEP = new_scope("STEP")
