from installers.machine_setup import install


if __name__ == "__main__":
    install(role="primary", label="Thor", peer_label="Loki", peer_ip="100.73.36.108")
