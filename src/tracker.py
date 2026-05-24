


from queue import Queue
from src.core.config import SessionConfig
from src.core.handler_thread import HandlerThread
from src.core.tracker_thread import TrackerThread
from src.core.writer_thread import WriterThread
from src.data_provider.factory import create_provider_threads 

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
       

        ## Fill in the args
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
        
        # Queue
        self.marker_queue = Queue(maxsize=100)
        
        self.writer_queue = Queue()
        self.event_sink = [self.writer_queue]
        
        # Load threads - provider factory returns a tuple with (provider,measurement_event)
        self.provider_threads = [
                    provider_factory(p_config) 
                    for p_config in self.session_config.provider_configs
                ]
                
        # self.guard_thread = create_guard_thread(session_config) 
        
        self.tracker_thread = TrackerThread(
                observer_config=self.session_config.observer_config,
                marker_queue = self.marker_queue,
            ) 
        
        
        self.handler_thread = HandlerThread(
            marker_queue= self.marker_queue,
            event_sink = self.event_sink,
            session_config = self.session_config,
            provider_threads = self.provider_threads,
        )
        
        self.writer_thread = WriterThread(
                    #config=self.session_config,
                    event_queue = self.writer_queue,
                )
        
        self.threads = [self.tracker_thread,self.writer_thread,*self.provider_threads, self.handler_thread]

        for thread in self.threads:
            thread.start()

            
            
    def epoch_start(self):
        self.tracker.epoch_start()
        
    def epoch_end(self):
        self.tracker.epoch_end()
        
    def stop(self):
        for thread in self.provider_threads:
            thread.stop()
            thread.join()

        self.tracker_thread.stop()
        self.guard_thread.stop()
        self.tracker_thread.join()
        self.guard_thread.join()

        self.writer_thread.stop() 
        self.writer_thread.join()

        return self._generate_session_report()

    def _generate_session_report(self):
        # Fetch the final aggregated data from the writer or tracker state
        # Returns a dataclass/dict with total energy, emissions, duration, etc.
        pass   