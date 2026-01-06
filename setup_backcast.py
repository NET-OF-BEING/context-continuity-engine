#!/usr/bin/env python3
"""
Setup Backcasting plan for Context Continuity Engine project
"""

import sys
sys.path.insert(0, '/home/panda/Documents/PythonScripts/OutcomeBackcasting')

from backcast_engine import (
    BackcastEngine, Outcome, Step, BackcastPlan,
    StepType, StepStatus, Priority
)

def main():
    engine = BackcastEngine()

    # Define the outcome
    print("Creating backcast for Context Continuity Engine...")
    outcome = Outcome(
        title="Context Continuity Engine - Fully Functional",
        description="Complete privacy-aware activity tracking system with semantic search, "
                   "temporal graphs, context prediction, and cross-device sync",
        success_criteria=[
            "Activity monitoring daemon running on system startup",
            "Vector embeddings for semantic context search",
            "Temporal graph tracking activity relationships",
            "Privacy controls blocking sensitive data",
            "Context prediction surfacing relevant info",
            "API server for cross-device sync",
            "CLI interface for queries and management"
        ],
        constraints=[
            "Privacy-first: local-only data storage",
            "OpenSUSE Linux compatibility required",
            "Minimal system resource usage",
            "No external API dependencies for core features"
        ],
        timeline="1 week"
    )

    # Create plan
    plan = BackcastPlan(outcome=outcome, steps=[])

    # Define steps
    steps_data = [
        {
            "id": 1,
            "title": "Project Setup",
            "description": "Set up project structure, venv, requirements.txt, config files",
            "status": StepStatus.COMPLETED,
            "priority": Priority.CRITICAL,
            "dependencies": []
        },
        {
            "id": 2,
            "title": "Database Layer",
            "description": "SQLite schema for activities, contexts, files, applications with full CRUD",
            "status": StepStatus.COMPLETED,
            "priority": Priority.CRITICAL,
            "dependencies": []
        },
        {
            "id": 3,
            "title": "Vector Embeddings Store",
            "description": "ChromaDB + SentenceTransformers for semantic similarity search",
            "status": StepStatus.IN_PROGRESS,
            "priority": Priority.HIGH,
            "dependencies": []
        },
        {
            "id": 4,
            "title": "Temporal Knowledge Graph",
            "description": "NetworkX graph with temporal relationships, decay, and predictions",
            "status": StepStatus.IN_PROGRESS,
            "priority": Priority.HIGH,
            "dependencies": []
        },
        {
            "id": 5,
            "title": "Privacy System",
            "description": "Blacklist apps/URLs/dirs, content filtering, privacy controls",
            "status": StepStatus.NOT_STARTED,
            "priority": Priority.CRITICAL,
            "dependencies": []
        },
        {
            "id": 6,
            "title": "Activity Monitor Daemon",
            "description": "X11 window tracking, file monitoring, app usage daemon",
            "status": StepStatus.NOT_STARTED,
            "priority": Priority.CRITICAL,
            "dependencies": [5]
        },
        {
            "id": 7,
            "title": "Context Prediction Engine",
            "description": "ML-based engine for predicting and surfacing relevant context",
            "status": StepStatus.NOT_STARTED,
            "priority": Priority.HIGH,
            "dependencies": [3, 4]
        },
        {
            "id": 8,
            "title": "API Server",
            "description": "FastAPI server for cross-device sync and external access",
            "status": StepStatus.NOT_STARTED,
            "priority": Priority.MEDIUM,
            "dependencies": [2]
        },
        {
            "id": 9,
            "title": "CLI Interface",
            "description": "Rich CLI for queries, stats, config management",
            "status": StepStatus.NOT_STARTED,
            "priority": Priority.HIGH,
            "dependencies": []
        },
        {
            "id": 10,
            "title": "Git Repository & Docs",
            "description": "Initialize git, create README, write documentation",
            "status": StepStatus.NOT_STARTED,
            "priority": Priority.LOW,
            "dependencies": []
        }
    ]

    # Create Step objects
    for step_data in steps_data:
        step = Step(
            id=step_data["id"],
            title=step_data["title"],
            description=step_data["description"],
            type=StepType.ACTION,
            priority=step_data["priority"],
            status=step_data["status"],
            estimated_duration="1-2 days",
            resources_needed=[],
            dependencies=step_data["dependencies"],
            success_criteria=[],
            risks=[]
        )
        plan.steps.append(step)
        print(f"  ✓ Added: {step.title} [{step.status.value}]")

    # Save the plan
    filename = "context_continuity_engine.json"
    filepath = engine.save_plan(plan, filename)

    print(f"\n✅ Backcast plan created successfully!")
    print(f"   Outcome: {outcome.title}")
    print(f"   Steps: {len(plan.steps)}")
    print(f"   Timeline: {outcome.timeline}")
    print(f"   Saved to: {filepath}")

    return filepath

if __name__ == '__main__':
    filepath = main()
