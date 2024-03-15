import inspect

def log(message):
    func = inspect.currentframe().f_back.f_code
    print("%s: %s" % (func.co_name, message))

