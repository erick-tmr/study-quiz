# TCP basics — study notes

## Connection establishment (three-way handshake)
1. Client sends SYN with its initial sequence number (ISN).
2. Server replies SYN-ACK: its own ISN and an ACK of the client's ISN + 1.
3. Client sends ACK of the server's ISN + 1.

Why three messages? Each side must announce its own ISN *and* learn that the
other side received it, so both directions are confirmed to work. Random ISNs
plus the handshake also stop old, delayed duplicate segments from a previous
connection being accepted as part of a new one.

## Reliability
TCP numbers every byte. The receiver sends cumulative ACKs; unacknowledged data is
retransmitted after a retransmission timeout (RTO) or after three duplicate ACKs
(fast retransmit).

## Flow control vs congestion control
- **Flow control** protects the *receiver*: the receive window (rwnd) advertised in
  every segment limits how much unacknowledged data the sender may have in flight.
- **Congestion control** protects the *network*: the sender keeps a congestion
  window (cwnd), grows it (slow start, then congestion avoidance) and shrinks it
  on loss. Effective window = min(rwnd, cwnd).

## Connection teardown
Each direction is closed independently with FIN / ACK (four segments in general).
The side that closes first waits in TIME_WAIT for 2×MSL so late segments die out
and its final ACK can be retransmitted if lost.
