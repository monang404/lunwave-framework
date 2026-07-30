# core module
#
# Phase 2 of the framework extraction (see docs/extraction/) moved the
# generic kernel primitives that used to live directly in this package
# (logging, observability, security, task_utils, mem_stats,
# latency_window, server_clock) into the `lunawave-framework` package.
# The files of the same names still here are backward-compat shims
# delegating to lunawave_framework.core.*.
#
# Phase 3 (domain-vocabulary split) also landed: state.py, events.py,
# commands.py, exceptions.py, ports.py, event_bus.py, command_bus.py are
# now backward-compat shims too, delegating to lunawave_framework.core.kernel
# (mechanism) and music.domain.* (vocabulary) -- see ADR 0013.
#
# Phase 4 (persistence split, ADR 0014) moved persistence/{db,session_repo,
# admin_account_repo}.py into lunawave_framework.core.storage the same way;
# those shims live in persistence/, not here, since they were never in core/.

