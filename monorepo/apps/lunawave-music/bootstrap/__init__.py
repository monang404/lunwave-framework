"""
Module: bootstrap

Purpose:
    Startup subsystems for main.py, split out of the former God Function
    `main()` (T2.4). Each stage lives in its own module and shares state via
    the `BootstrapContext` singleton defined in `bootstrap.services`.

Responsibilities:
    - Re-export nothing by default; import the stage module you need
      (services, startup_tasks, maintenance) explicitly.

Depends on:
    None

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Main thread (async event loop).
"""
