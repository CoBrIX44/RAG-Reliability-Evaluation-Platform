# Observed execution environment

Observed at 2026-10-17T10:22:28.4853956Z; this is a current machine/resource observation, not proof of an identical historical load or controlled timing acquisition.

| Item | Observed value |
|---|---|
| Host CPU | AMD Ryzen 7 9800X3D 8-Core Processor |
| Physical/logical cores | 8/16 |
| Host physical memory | 33407352832 bytes |
| Host OS | Microsoft Windows 11 Pro, version 10.0.26300, build 26300 |
| Docker engine |29.8.2 |
| Docker Linux logical CPUs |16 |
| Docker Linux memory |16,298,962,944 bytes |
| Kernel |6.18.54.1-microsoft-standard-WSL2 |
| Worker configured limit |4 CPUs /4 GiB; one worker process |
| Model execution |Local CPU, generation threads2 /embedding threads2 |
| Python |3.12.13 in frozen API/worker runtime |
| Source identity |1123f6e613ba27ca7a9b1a97bbabe3159d6d074e1d101c8db8fbff041cda0f5e |

The model child starts per inference call; timing includes model hashing/loading. Shared preparation and queue time are excluded from question timers. Docker recovery and machine shutdown interrupt wall-clock run windows. Native tests, UI and other host activity can contend with inference. Cache state, energy use and financial/hardware cost are unmeasured. Timing is descriptive, not a cold/warm comparison or portable performance guarantee.

The30-case development inspection has a22.47-second median question timer (16.88–32.40-second observed range). These selected traces come from only two completed configurations. A remaining-work estimate based on this median is a planning extrapolation, not an ETA guarantee; reranking and recovery may take longer. Final reports must use actual saved timing samples/counts.
