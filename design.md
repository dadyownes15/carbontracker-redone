# Achitectural overview:

monitor | monitor() -> Project -> TrackerSession 
  create trackersession with gaurd 

  return TrackerSession 
      
detect -> Project -> display(Devices, IntensityProvider) 
  - create devices
  - create intensity provider

watch -> (something?) -> tui_display_live
  - create reader 
  - create  TrackerSession from read(output_path.x) 
  - tui_display_live( TrackerSession)
  
track | track()
  - create TrackerSession with no gaurd 
  - return 
  
# Core classes 
    
TrackerSession(Run):
  - load project
  - Create configs from run
  - creates PredictionEngine 
  - creates Emissions 
  - creates Measurements
  - creates ProgressTracker
  - creates Gaurd 
    - constructed from PredictionEngine and PolicyBudget
  - spawn TrackerThread(Sampler, ProgressTracker, Gaurd, GaurdHandler) 
  

TrackerThread()
  def start:
    # Unit increase should strigger some kind of way we can listen for. pretty sur ethat threads use some kind of block or something
    progressTracker.init()
    
    unit_increase:
      samples = sampler.pick()
      samples.write()
      command = Gaurd.check(samples)

      # Command could be to paus the training, and prompt the user. It could be to stop, warn, etc 
      if command is None:
        continue?
      else: 
        do(command)
    
      
Project
  - Stores api_key reference 
  - Project Name
  - Output location
  - Stores Defaults configs
  
  create_default()
  
  init_project()
  
  _save()


ProjectConfig
  - name
  - api_key_reference
  - Default log_dir
  
SessionConfig
  - Run name
  - Measurement config
  - Emissions config
  - Gaurd Config
  - Prediction Config
  - Budget Policy
  - Project Config
  - log_dir
  - flush_interval
  
Measurement Config
  - components = [cpu,ram,gpu] 
  - Sample interval
  - PUE
  - pids
  - devices_by_pid
  - simulated_component tuple[SimulatedComponent]
  
Emissions config:
  - Method: electricityMaps | static | auto | custom   
  - Location
  - Sample interval 
  - provider_key_ref?
  - static_carbon_intensity_g_per_kwh

ProgressConfig:
  - unit_kid: str = "epoch"
  - total_units
  - autodetect 
  - unit_marker 
  
Prediction config:
  - enabled
  - predict_after
  - estimator: Literal["mean"]
  - confidence_intervals: bool = True
  - validate_at_end: bool = False 

BudgetBudgetPolicy
  - max_intensity 
  - max_energy_kwh
  - max_emissions_g
  - max_duration_s
  - action = ['raise','warn','stop','checkpoint_and_stop'] = 'warn' 
  - Callbacks []
  - use_upper_bound_se: True
  - patience: 2



## TUI

carbontracker init - tui -> setupWizard

carbontracker detect -> printout
carbontracker track ->  printout


carbontracker watch -> watchTui
carbontracker monitor -> perhabs tui? this is where they do continue xx

