Satellite Composites
====================

Overview of all nine Twilight satellite composites, what each one reveals scientifically, and how to select and compare them in the web UI.

Twilight supports nine satellite composites derived from Himawari-8/9 AHI data. Each composite highlights a different physical property of the atmosphere or Earth's surface, making it suited to specific monitoring scenarios.

Composite Reference
-------------------

ir_clouds — Infrared clouds
~~~~~~~~~~~~~~~~~~~~~~~~~~~

**What it shows:** Thermal infrared radiance from AHI band 13 (~10.4 µm). Cooler (higher-altitude) cloud tops appear brighter; warmer (lower-altitude) or cloud-free surfaces appear darker.

**Best use cases:**

* Continuous cloud detection at any time of day or night
* Tracking convective storm tops and estimating cloud-top height
* Monitoring tropical cyclone structure

true_color — True color
~~~~~~~~~~~~~~~~~~~~~~~

**What it shows:** A natural-color composite using visible and near-infrared channels during the day, blended with thermal infrared for night coverage. Daytime areas appear in familiar RGB color; nighttime areas show thermal emission.

**Best use cases:**

* General situational awareness and public-facing imagery
* Smoke, dust, and large-scale weather pattern visualization
* Day/night boundary monitoring

ash — Volcanic ash
~~~~~~~~~~~~~~~~~~

**What it shows:** A RGB composite using differences between thermal infrared channels to detect volcanic ash and SO₂. Ash-laden plumes appear in distinctive colors that distinguish them from water-ice clouds.

**Best use cases:**

* Detecting and tracking volcanic eruption plumes
* Aviation hazard monitoring
* Distinguishing ash from meteorological cloud

airmass — Air mass
~~~~~~~~~~~~~~~~~~

**What it shows:** A RGB composite built from water vapor and ozone absorption channels. Different air mass types — polar, tropical, and dynamic tropopause regions — appear in contrasting colors.

**Best use cases:**

* Identifying jet streams and potential rapid cyclogenesis zones
* Distinguishing dry intrusions from moist tropical air
* Supporting synoptic-scale weather analysis

day_microphysics — Day microphysics
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**What it shows:** A RGB composite using near-infrared and shortwave infrared channels to reveal cloud particle phase and size during daylight hours. Water clouds appear differently from ice clouds.

**Best use cases:**

* Distinguishing water droplet clouds from ice crystal clouds
* Identifying fog and low stratus
* Supporting precipitation nowcasting

night_microphysics — Night microphysics
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**What it shows:** A RGB composite using thermal infrared and split-window channels to reveal cloud microphysics at night, replacing solar-dependent channels with emissive channels.

**Best use cases:**

* Fog and low cloud detection after dark
* Nighttime identification of ice vs. water cloud tops
* Continuous 24-hour microphysics monitoring alongside the day variant

fog — Fog
~~~~~~~~~

**What it shows:** A RGB composite designed to highlight low-level fog and stratus by exploiting the difference between shortwave and thermal infrared channels, where fog strongly absorbs shortwave IR at night.

**Best use cases:**

* Fog detection and nowcasting for aviation and ground transport
* Early morning stratus monitoring
* Identifying sea fog over coastal regions

convection — Convection
~~~~~~~~~~~~~~~~~~~~~~~

**What it shows:** A RGB composite using water vapor and infrared channel differences to highlight deep convective activity, overshooting tops, and rapidly developing thunderstorms.

**Best use cases:**

* Identifying severe storm initiation and growth
* Monitoring overshooting convective tops
* Nowcasting for aviation turbulence and lightning risk

water_vapor — Differential  water vapor
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**What it shows:** A composite analysis of the vertical moisture gradient. It combines the upper-level (6.2 µm) and mid-level (7.3 µm) water vapor channels to distinguish 
the depth and altitude of moisture. **Green** tones typically represent high-level moisture/clouds, while **blue** tones indicate mid-to-lower level moisture.

**Best use cases:**

* **Differentiating vertical moisture layers:** Identifying whether a cloud or moisture plume resides in the upper or mid-troposphere.
* **Tracking deep convective moisture:** Identifying areas where moisture is present through a deep layer of the atmosphere (appearing as bright white/cyan).
* **Identifying mid-level dry slots:** Detecting regions where the upper levels may be moist (e.g., cirrus clouds) but the middle levels are significantly drier.
* **Refining frontal boundaries:** Visualizing the transition between different air masses based on their specific vertical moisture signatures.

Selecting Composites in the Web UI
----------------------------------

The composite selector appears in the toolbar at the top of the map. Click it to open the dropdown, then click any composite name to display it on the map.

**To select a composite:**

1. Click the composite dropdown button in the top toolbar.
2. Click any composite name in the list.
3. A check mark appears next to the active selection. The map updates immediately.

**To enable multi-select for side-by-side mode:**

Hold **Ctrl** while clicking a second composite to add it to the selection. Up to two composites can be selected at once.

Press **Escape** or click anywhere outside the dropdown to close it without changing the selection.

Side-by-side Comparison Mode
----------------------------

When two composites are selected, Twilight activates side-by-side comparison mode. A draggable vertical divider splits the map: the left composite fills the left half and the right composite fills the right half.

* Drag the divider left or right to change the split point.
* Map pan and zoom remain synchronized across both layers.
* To exit comparison mode, hold **Ctrl** and click the second composite to deselect it.

Side-by-side mode uses the same timestamp for both composites. Use the time selector to navigate to the period you want to compare.

Limiting Which Composites Are Processed
---------------------------------------

By default the server and worker process all nine composites. You can restrict this set with the ``AVAILABLE_COMPOSITES`` environment variable, which accepts a comma-separated list.

.. code-block:: bash

   # Server — controls which composites the API accepts
   AVAILABLE_COMPOSITES=ir_clouds,true_color,ash

   # Worker — controls which composites the task generator enqueues
   AVAILABLE_COMPOSITES=ir_clouds,true_color,ash

Set the variable to the same value in both the server and worker environments. The server rejects requests for composites that are not in its list, and the task generator only creates tasks for composites in its list.

.. warning::

   If the server's ``AVAILABLE_COMPOSITES`` is narrower than the worker's, the worker may create tasks that the server will refuse. Keep both lists in sync.
