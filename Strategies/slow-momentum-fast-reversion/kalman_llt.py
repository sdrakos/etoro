"""Local-linear-trend Kalman filter (pure numpy, no IO).
State x=[level, velocity]; F=[[1,1],[0,1]], H=[1,0]. Returns belief read-offs:
filtered level, trend velocity, trend significance (t-stat), standardized innovation."""
from __future__ import annotations
import numpy as np


def kalman_llt(log_price, q_level=1e-5, q_vel=1e-7, r_obs=1e-6, init_var=1.0):
    y = np.asarray(log_price, dtype=float)
    T = len(y)
    F = np.array([[1.0, 1.0], [0.0, 1.0]])
    H = np.array([[1.0, 0.0]])
    Q = np.array([[q_level, 0.0], [0.0, q_vel]])
    x = np.array([[y[0]], [0.0]])
    P = np.eye(2) * init_var

    level = np.empty(T); vel = np.empty(T); vel_var = np.empty(T)
    innov = np.empty(T); innov_var = np.empty(T)
    for t in range(T):
        x = F @ x                       # predict state
        P = F @ P @ F.T + Q             # predict covariance
        nu = y[t] - (H @ x)[0, 0]       # innovation
        S = (H @ P @ H.T)[0, 0] + r_obs
        K = (P @ H.T) / S               # 2x1 gain
        x = x + K * nu                  # update state
        P = (np.eye(2) - K @ H) @ P     # update covariance
        level[t] = x[0, 0]; vel[t] = x[1, 0]; vel_var[t] = P[1, 1]
        innov[t] = nu; innov_var[t] = S

    return {
        "level": level, "velocity": vel, "vel_var": vel_var,
        "innovation": innov, "innov_var": innov_var,
        "trend_sig": vel / np.sqrt(vel_var + 1e-12),
        "std_innov": innov / np.sqrt(innov_var + 1e-12),
    }
