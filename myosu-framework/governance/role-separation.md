# Role Separation

John performs both authorial and system-design functions. These roles
are separated in process.

## Author Role (John as Author)
- Defines research direction and interpretive frames
- Reviews and approves/rejects agent outputs
- Promotes agent synthesis to human-author spaces
- Conducts pre-publication provenance audits
- Runs weekly/quarterly governance checks
- Signs accountability statement

## Builder Role (John as System Designer)
- Modifies agent prompts, models, and capabilities
- Changes governance configuration thresholds
- Adds or removes agent roles
- Updates the provenance schema
- Writes and maintains acceptance tests
- Deploys new pipeline versions

## Separation Rule
A builder action cannot count as authorial endorsement unless explicitly
marked as such. System changes made by "builder John" are not automatically
approved by "author John." Each role's decisions are recorded as distinct
acts in the governance log.

When John changes the system and then uses the changed system, the change
must be logged before the use. The log entry serves as the role boundary.
