import logging
from queue import Queue
import threading
from threading import Event
from src.core.config import SessionConfig, ProviderType, SessionMode
from src.core.aggregator_thread import AggregatorThread
from src.observer.factory import observer_factory
from src.core.terminal_output_thread import TerminalOutputThread
from src.core.file_logger_thread import FileLoggerThread
from src.data_provider.factory import provider_factory 
from src.core.logging_handler import EventQueueLogHandler
from src.core.exceptions import WrongModeError
from src.core.execution_guard import GuardVerdict

class CarbonTracker:
    """

    The CarbonTracker class is the main interface for starting, stopping and reporting through **carbontracker**.

    Args:
        epochs (int): Total epochs of your training loop.
        api_keys (dict, optional): Dictionary of Carbon Intensity API keys following the {name:key} format. 
            Example: `{ \\"electricitymaps\\": \\"abcdefg\\" }`
        epochs_before_pred (int, optional): Epochs to monitor before outputting predicted consumption. Set to -1 for all epochs. Set to 0 for no prediction.
        monitor_epochs (int, optional): Total number of epochs to monitor. Outputs actual consumption when reached. Set to -1 for all epochs. Cannot be less than `epochs_before_pred` or equal to 0.
        update_interval (int, optional): Interval in seconds between power usage measurements are taken by sleeper thread.
        interpretable (bool, optional): If set to `True` then the CO2eq are also converted to interpretable numbers such as the equivalent distance travelled in a car, etc. Otherwise, no conversions are done.
        stop_and_confirm (bool, optional): If set to `True` then the main thread (with your training loop) is paused after epochs_before_pred epochs to output the prediction and the user will need to confirm to continue training. Otherwise, prediction is output and training is continued instantly.
        ignore_errors (bool, optional): If set to `True` then all errors will cause energy monitoring to be stopped and training will continue. Otherwise, training will be interrupted as with regular errors.
        components (str, optional): Comma-separated string of which components to monitor. Options are: `"all"`, `"gpu"`, `"cpu"`, or `"gpu,cpu"`.
        devices_by_pid (bool, optional): If `True`, only devices (under the chosen components) running processes associated with the main process are measured. If False, all available devices are measured. Note that this requires your devices to have active processes before instantiating the CarbonTracker class.
        log_dir (str, optional): Path to the desired directory to write log files. If `None`, then no logging will be done.
        log_file_prefix (str, optional): Prefix to add to the log file name.
        verbose (int, optional): Sets the level of verbosity.
        decimal_precision (int, optional): Desired decimal precision of reported values.
        sim_cpu (float, optional): Custom CPU value for components.
        sim_cpu_tdp (float, optional): Custom TDP value for components.
        sim_cpu_util (float, optional): Custom CPU utilization for components.
        sim_gpu (float, optional): Custom GPU value for components.
        sim_gpu_watts (float, optional): Custom GPU Watts value for components.
        sim_gpu_util (float, optional): Custom GPU utilization for components.

    Example:
        Tracking the carbon intensity of PyTorch model training:

            from carbontracker.tracker import CarbonTracker

            tracker = CarbonTracker(epochs=max_epochs)
            # Training loop.
            for epoch in range(max_epochs):
                tracker.epoch_start()
                # Your model training.
                tracker.epoch_end()

            # Optional: Add a stop in case of early termination before all monitor_epochs has
            # been monitored to ensure that actual consumption is reported.
            tracker.stop()

    """

    def __init__(
        self,
        epochs,
        epochs_before_pred=1,
        monitor_epochs=-1,
        update_interval=1,
        interpretable=True,
        stop_and_confirm=False,
        ignore_errors=False,
        components="all",
        devices_by_pid=False,
        log_dir=None,
        log_file_prefix="",
        verbose=1,
        decimal_precision=12,
        api_keys=None,
        sim_cpu=None,
        sim_cpu_tdp=None,
        sim_cpu_util=None,
        sim_gpu=None,
        sim_gpu_watts=None,
        sim_gpu_util=None
    ):
       
        self.session_config = SessionConfig.from_legacy_args(
                    epochs=epochs,
                    epochs_before_pred=epochs_before_pred,
                    monitor_epochs=monitor_epochs,
                    update_interval=update_interval,
                    interpretable=interpretable,
                    stop_and_confirm=stop_and_confirm,
                    ignore_errors=ignore_errors,
                    components=components,
                    devices_by_pid=devices_by_pid,
                    log_dir=log_dir,
                    log_file_prefix=log_file_prefix,
                    verbose=verbose,
                    decimal_precision=decimal_precision,
                    api_keys=api_keys,
                    sim_cpu=sim_cpu,
                    sim_cpu_tdp=sim_cpu_tdp,
                    sim_cpu_util=sim_cpu_util,
                    sim_gpu=sim_gpu,
                    sim_gpu_watts=sim_gpu_watts,
                    sim_gpu_util=sim_gpu_util
                )
        
        # Queues
        self.aggregation_queue = Queue()
        self.terminal_queue = Queue()
        self.logger_queue = Queue()
        self.event_sink = [self.terminal_queue, self.logger_queue]
        
        self._setup_logging()
        
        # Build provider threads with shared trigger events
        self.provider_threads = []
        self.provider_trigger_events = []
        
        for p_config in self.session_config.provider_configs:
            trigger = Event()
            self.provider_trigger_events.append(trigger)
            self.provider_threads.append(
                provider_factory(p_config, self.aggregation_queue, trigger)
            )
        
        self.observer_thread = observer_factory(
            config=self.session_config.observer_config,
            mode=self.session_config.mode,
            aggregation_queue=self.aggregation_queue,
            event_sink=self.event_sink,
            notify_events=self.provider_trigger_events
        )
        
        self._guard_triggered = Event()
        self._guard_verdict = None
        
        def _default_guard_callback(verdict: GuardVerdict):
            # TODO (dadyownes15):
            # Add proper gaurd callbacks that match the config
            self._guard_verdict = verdict
            self._guard_triggered.set()
            self.logger.warn("Budget has been violated: ", verdict.reason)
        
        self.aggregator_thread = AggregatorThread(
            prediction_config=self.session_config.prediction_config,
            budget_policy=self.session_config.budget_policy,
            stats_emit_interval_s=self.session_config.stats_emit_interval_s,
            mode=self.session_config.mode,
            aggregation_queue=self.aggregation_queue,
            event_sink=self.event_sink,
            guard_callback=_default_guard_callback if self.session_config.mode.is_python else None
        )
        
        self.terminal_thread = TerminalOutputThread(
            log_level=self.session_config.log_level,
            event_queue=self.terminal_queue
        )
        self.logger_thread = FileLoggerThread(
            log_dir=self.session_config.log_dir,
            run_name=self.session_config.run_name,
            event_queue=self.logger_queue
        )
        
        # Order is important here for proper closedown
        self.threads = [
            self.observer_thread, 
            *self.provider_threads, 
            self.aggregator_thread,
            self.terminal_thread, 
            self.logger_thread, 
        ]

        for thread in self.threads:
            thread.start()

        self.logger.debug("Active threads list:")
        for thread in threading.enumerate():
            self.logger.debug(f" - Name: {thread.name}, ID: {thread.native_id}, Daemon: {thread.daemon}")

    def _setup_logging(self):
        self.logger = logging.getLogger("carbontracker")
        self.logger.setLevel(self.session_config.log_level)
        self.logger.propagate = False 
        self.logger.handlers.clear()

        queue_handler = EventQueueLogHandler(self.event_sink)
        formatter = logging.Formatter('%(message)s')
        queue_handler.setFormatter(formatter)
        self.logger.addHandler(queue_handler)
            
    def epoch_start(self):
        if self.session_config.mode != SessionMode.PYTHON_MANUAL:
            raise WrongModeError("epoch_start() is only available in python-manual mode")
        self.observer_thread.manual_start()
        
    def epoch_end(self):
        if self.session_config.mode != SessionMode.PYTHON_MANUAL:
            raise WrongModeError("epoch_start() is only available in python-manual mode") # using proper exception later
        self.observer_thread.manual_end()
        
    def finish(self):
        final_stats = None
            
        for thread in self.threads:
            result = thread.stop()
            if isinstance(thread, AggregatorThread):
                final_stats = result
            thread.join()
            
        for thread in threading.enumerate():
            self.logger.debug("f - Name: {thread.name}, ID: {thread.native_id}, Daemon: {thread.daemon}")
            
        return final_stats
