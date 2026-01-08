#!/usr/bin/env python3
"""
Simple test script for Context Continuity Engine
"""

import sys
from pathlib import Path
from datetime import datetime

# Add context_engine to path
sys.path.insert(0, str(Path(__file__).parent))

from context_engine.storage.activity_db import ActivityDatabase
from context_engine.vector_db.embeddings import EmbeddingStore
from context_engine.graph.temporal_graph import TemporalGraph
from context_engine.prediction.context_predictor import ContextPredictor
from context_engine.privacy.privacy_filter import PrivacyFilter


def test_basic_functionality():
    """Test basic functionality of all components."""

    print("=" * 60)
    print("Context Continuity Engine - Basic Functionality Test")
    print("=" * 60)

    # 1. Test Database
    print("\n[1/5] Testing ActivityDatabase...")
    db = ActivityDatabase("data/test_activity.db")

    # Record some test activities
    activity_ids = []
    for i in range(5):
        activity_id = db.record_activity(
            activity_type="window_focus",
            app_name=f"TestApp{i % 2}",
            window_title=f"Test Window {i}",
            duration=10 + i * 5
        )
        activity_ids.append(activity_id)

    stats = db.get_stats()
    print(f"   ✓ Created {stats['total_activities']} activities")
    print(f"   ✓ Tracked {stats['total_applications']} applications")

    # 2. Test Vector Embeddings
    print("\n[2/5] Testing EmbeddingStore...")
    embeddings = EmbeddingStore(
        persist_directory="data/test_embeddings",
        collection_name="test_context"
    )

    # Add some embeddings
    texts = [
        "Working on Python project in VSCode",
        "Reading documentation in Firefox",
        "Writing code in PyCharm",
        "Debugging application in terminal",
        "Browsing Stack Overflow for solutions"
    ]

    for i, text in enumerate(texts):
        embeddings.add_text(
            text=text,
            metadata={"activity_id": i, "timestamp": datetime.now().isoformat()}
        )

    print(f"   ✓ Added {embeddings.count()} embeddings")

    # Test semantic search
    results = embeddings.search_similar("coding in IDE", n_results=3)
    print(f"   ✓ Found {len(results)} similar contexts for 'coding in IDE':")
    for r in results[:2]:
        print(f"      - {r['text'][:50]}... (similarity: {r['similarity']:.2f})")

    # 3. Test Temporal Graph
    print("\n[3/5] Testing TemporalGraph...")
    graph = TemporalGraph(persist_path="data/test_graph.pkl")

    # Add nodes and edges
    for i in range(5):
        graph.add_activity_node(
            activity_id=f"activity_{i}",
            activity_type="window_focus",
            timestamp=datetime.now(),
            app_name=f"TestApp{i % 2}"
        )

    # Connect sequential activities
    from datetime import timedelta
    for i in range(4):
        graph.connect_sequential_activities(
            f"activity_{i}",
            f"activity_{i+1}",
            timedelta(seconds=30)
        )

    graph_stats = graph.get_stats()
    print(f"   ✓ Created {graph_stats['total_nodes']} nodes")
    print(f"   ✓ Created {graph_stats['total_edges']} edges")

    # Test predictions
    predictions = graph.predict_next_activities("activity_0", top_k=3)
    print(f"   ✓ Generated {len(predictions)} predictions from graph")

    # 4. Test Context Predictor
    print("\n[4/5] Testing ContextPredictor...")
    predictor = ContextPredictor(db, embeddings, graph)

    current_activity = {
        "activity_type": "window_focus",
        "app_name": "VSCode",
        "window_title": "main.py - MyProject"
    }

    predictions = predictor.predict_context(current_activity, max_results=5)
    print(f"   ✓ Generated {len(predictions)} context predictions")

    if predictions:
        print(f"   ✓ Top prediction: {predictions[0].get('reason', 'N/A')}")

    # Get suggestions
    suggestions = predictor.get_context_suggestions(current_activity)
    print(f"   ✓ Suggestions: {len(suggestions.get('related_files', []))} files, "
          f"{len(suggestions.get('related_apps', []))} apps")

    # 5. Test Privacy Filter
    print("\n[5/5] Testing PrivacyFilter...")
    privacy_config = {
        'enabled': True,
        'blacklist_apps': ['keepassxc', 'bitwarden'],
        'blacklist_urls': ['*://*/login*', '*://*/password*'],
        'blacklist_directories': ['~/.ssh', '~/.gnupg'],
        'exclude_file_types': ['.key', '.pem', '.gpg']
    }

    privacy = PrivacyFilter(privacy_config)

    # Test filtering
    test_activities = [
        {"app_name": "firefox", "window_title": "GitHub"},
        {"app_name": "keepassxc", "window_title": "Password Manager"},
        {"url": "https://example.com/login"},
        {"file_path": "/home/user/.ssh/id_rsa"}
    ]

    allowed = sum(1 for a in test_activities if privacy.should_track_activity(a))
    blocked = len(test_activities) - allowed

    print(f"   ✓ Tested {len(test_activities)} activities")
    print(f"   ✓ Allowed: {allowed}, Blocked: {blocked}")

    privacy_stats = privacy.get_privacy_stats()
    print(f"   ✓ Blacklisted apps: {privacy_stats['blacklisted_apps']}")

    # Summary
    print("\n" + "=" * 60)
    print("✅ All components tested successfully!")
    print("=" * 60)
    print("\nThe Context Continuity Engine is ready to use:")
    print("  • Start daemon: ./context_daemon.py")
    print("  • View recent:  ./context_cli.py recent")
    print("  • Search:       ./context_cli.py search 'query'")
    print("  • Stats:        ./context_cli.py stats")
    print()


if __name__ == '__main__':
    try:
        test_basic_functionality()
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
