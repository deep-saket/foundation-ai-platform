import docker # for docker-py SDK
import yaml # for parsing vllm_config.yaml

class DockerManager: # Object managing Docker containers
	def __init__(self, config_path: str): # constructor; runs auto whenever DockerManager object created

		self.client = docker.from_env() # connects brev env var to Daemon and saves this connection as self.client
		
		# Open yaml, converts text to dict and extracts data under "serving:" header; saves into self.config
		with open(config_path, 'r') as file:
			self.config = yaml.safe_load(file)['serving']

	def start_vllm_server(self):
		
		print(f"Starting vLLM container with {self.config['model_name']} model loaded.")
		
		# SDK's way of requesting Daemon access to all GPUs
		device_request = docker.types.DeviceRequest(count=-1, capabilities=[['gpu']])

		try:
			container = self.client.containers.run(
				image=self.config['engine_image'],
				command=f"--model {self.config['model_name']} --port {self.config['port']}",
				name=self.config['container_name'],
				detach=True,
				network_mode="host",
				volumes={
					self.config['volumes']['host_path']: {
						'bind': self.config['volumes']['container_path'],
						'mode': 'rw'
					}
				},
				device_requests=[device_request]
			)
			
			print(f"Container {container.name} is starting.")
			return container

		except docker.errors.APIError as e:
			print(f"Failed to start container: {e}")
			return None


