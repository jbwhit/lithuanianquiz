# Lithuanian Language Learning App PRD

## Context & Problem Statement
Learning Lithuanian presents unique challenges due to its complex grammatical cases and number-related expressions. Students must master various grammatical forms while simultaneously learning how to express and understand numbers in different contexts (prices, ages, times, years). Currently, existing solutions don't effectively adapt to individual learning patterns or systematically address these interconnected challenges.

### Current Examples
The app currently supports exercises like:
- Price questions using different grammatical cases
  - "Kiek kainuoja žurnalas? (€2)" - requiring accusative case
  - "Kokia kaina? (€61)" - requiring nominative case
- Planned extensions include questions about:
  - Ages (e.g., "He is 6 years old")
  - Time
  - Years (e.g., historical dates like 1941)

## Proposed Solution
A Lithuanian learning application that uses adaptive learning techniques to help users master both numerical expressions and their associated grammatical forms.

### Core Features

#### 1. Hierarchical Exercise System
The system organizes exercises in a multi-level hierarchy:
- Top-level categories (e.g., "Numbers")
- Exercise types (e.g., "Prices," "Ages," "Time," "Years")
- Specific exercise patterns (e.g., "kiek_kainuoja," "kokia_kaina")
- Grammatical cases (e.g., accusative, nominative)
- Number patterns (e.g., decades, single digits, special patterns)

#### 2. Adaptive Learning Engine
Implements Thompson sampling to:
- Track user performance across all hierarchical levels
- Generate questions that target:
  - Individual weak areas (e.g., numbers in the 30s)
  - Grammatical cases (e.g., accusative)
  - Combinations of weak areas (e.g., accusative case with numbers in the 30s)
- Maintain learning history to optimize question selection

#### 3. Performance Tracking System
Monitors and analyzes:
- Success rates by exercise type
- Success rates by grammatical case
- Success rates by number pattern
- Combined performance metrics for pattern combinations
- Overall progress and proficiency levels

### Key Requirements

#### Exercise Generation
- Must support dynamic generation of exercises based on performance metrics
- Should combine multiple aspects (grammar, numbers) in a natural way
- Must maintain grammatical accuracy across all generated exercises

#### Performance Tracking
- Must track performance at all hierarchical levels
- Should identify patterns in user mistakes
- Must support both isolated and combined performance metrics
- Should track progress over time

#### Adaptive Algorithm
- Must implement Thompson sampling to optimize exercise selection
- Should balance exploration (trying new patterns) with exploitation (reinforcing weak areas)
- Must consider both individual aspects and their combinations
- Should adapt to improving or declining performance

### Future Considerations

#### Potential Expansions
- Additional grammatical cases and constructions
- More complex number usage scenarios
- Integration with vocabulary learning
- Spaced repetition features
- Difficulty progression system

#### Technical Considerations
- System must be designed to easily accommodate new exercise types
- Performance metrics should be stored efficiently for quick retrieval
- Exercise generation should be modular and extensible

## Success Metrics
- Improved user accuracy in target areas
- Reduced time to mastery for common number expressions
- User engagement and retention
- Coverage of different grammatical cases and number patterns
- Accuracy of the adaptive system in identifying and addressing weak areas

## Rollout Strategy
1. Initial release with price-related exercises
2. Addition of age-related exercises
3. Integration of time-telling exercises
4. Addition of year/date exercises
5. Continuous refinement of adaptive algorithm based on user data

## Next Steps
1. Implement basic exercise structure and tracking system
2. Develop and test Thompson sampling implementation
3. Create initial set of exercises for prices
4. Test adaptive learning effectiveness
5. Gather user feedback and iterate
