


Review if parts can be outsourced to dependencies and if code and tests can be simplified in general, if new dependencies need to be included, weight the gains carefully
See if similar solutions can be merged and remove unused functions and information

---

create a comprehensive usage, getting started and other operational documentation under docs/
Minimize duplication against product breakdown structure and make sure information has one canonical source.
This to enable usage, ease of access to developers and users and increased onboarding

---


Implement IMP-025 with the fork and and try to minimize as much manual parsing/usage of xml or artifacts as possible.

some changes to the repository: `https://github.com/jkCXf9X4/pyssp_standard` (branch: `architecture_review`) has been registered, please ensure that all aspects are aligned with the improvement work

try to utilize the venv for local development to not pollute the global pip 


--- 

are there any parts of this codebase that falls into the domain of pyssp_standard? please create a improvement list that can provide input for future features for pyssp_standard