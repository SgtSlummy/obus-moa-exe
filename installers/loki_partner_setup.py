from installers.machine_setup import install


if __name__ == "__main__":
    install(role="worker", label="Loki", peer_label="Thor", peer_ip="100.67.26.14")
