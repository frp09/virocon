"""
Fit an exponentiated Weibull distribution to a significant wave height dataset.
"""

import numpy as np
import matplotlib.pyplot as plt

from virocon import ExponentiatedWeibullDistribution, read_ec_benchmark_dataset


# Load sea state measurements from the NDBC buoy 44007.
data = read_ec_benchmark_dataset("datasets/ec-benchmark_dataset_A_1year.txt")
hs = data["Significant wave height (m)"].to_numpy()

# Fit the exponentiated Weibull distribution to the measurements.
dist = ExponentiatedWeibullDistribution()
dist.fit(hs)

# Print the distribution object, which outputs the estimated parameters.
print(dist)

# Plot the density of the empirical distribution and the fitted distribution.
fig, ax = plt.subplots(1, 1)
plt.hist(hs, bins=20, density=True, label="Empirical distribution")
x = np.linspace(0, max(hs), 200)
plt.plot(x, dist.pdf(x), label="Fitted distribution")
plt.xlabel("Significant wave height (m)")
plt.ylabel("Probability density (-)")
ax.legend()
#plt.savefig("virocon_exponentiated_weibull.pdf", dpi=300, bbox_inches='tight', pad_inches=0)
plt.show()
