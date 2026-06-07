# Experimental architecture

This directory should store diagrams and descriptions of the architecture used in the article.

Recommended diagrams:

- k6 load client for C1, C2, and C3;
- k6 load client for C4 on AWS;
- metric flow between Node Exporter, cAdvisor, Prometheus, and Grafana;
- network topology and exposed ports.

In the recommended architecture, the test client runs only k6. Prometheus and Grafana stay on the local server with the monitoring infrastructure, not on the notebook/k6 client.

For C4, avoid representing Node Exporter and cAdvisor as public endpoints. If Prometheus stays in the local environment, show a VPN, SSH tunnel, or another controlled connection. The recommended flow in this repository is documented in `docs/aws-ssh-tunnel-prometheus.md`.

Use placeholders for IPs, DNS names, and AWS identifiers until the final environment is defined.
