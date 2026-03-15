# seed_data.py
import sys, os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer
import uuid
import config

COURSE_ID   = "CS301"
EMBED_MODEL = config.EMBED_MODEL   # all-MiniLM-L6-v2 → 384-dim vectors

TEST_CHUNKS = [
    # Chapter 1
    {
        "text": "Big-O notation describes the upper bound of an algorithm's "
                "time complexity. O(1) is constant time, O(log n) is "
                "logarithmic, O(n) is linear, O(n log n) is linearithmic, "
                "O(n^2) is quadratic, and O(2^n) is exponential.",
        "chapter": "Chapter 1", "filename": "lecture1_bigo.pdf", "page": 1
    },
    {
        "text": "To calculate Big-O, we drop constants and lower-order terms. "
                "For example, 3n^2 + 5n + 100 simplifies to O(n^2). We care "
                "about the dominant term because as n approaches infinity "
                "smaller terms become negligible. This is asymptotic analysis.",
        "chapter": "Chapter 1", "filename": "lecture1_bigo.pdf", "page": 2
    },
    {
        "text": "Best case, worst case, and average case complexity are "
                "different measures. Big-O typically describes the worst case. "
                "Linear search has O(n) worst case when the element is at the "
                "end or not present, but O(1) best case when it is first.",
        "chapter": "Chapter 1", "filename": "lecture1_bigo.pdf", "page": 3
    },
    # Chapter 2
    {
        "text": "Bubble sort repeatedly swaps adjacent elements that are in "
                "the wrong order. It has O(n^2) time complexity in the worst "
                "and average case, and O(n) in the best case when the array "
                "is already sorted. Space complexity is O(1) in-place.",
        "chapter": "Chapter 2", "filename": "lecture2_sorting.pdf", "page": 1
    },
    {
        "text": "Merge sort uses a divide and conquer approach. It divides "
                "the array into two halves, recursively sorts each half, "
                "then merges them. Time complexity is O(n log n) in all cases. "
                "Requires O(n) extra space for temporary arrays during merging.",
        "chapter": "Chapter 2", "filename": "lecture2_sorting.pdf", "page": 2
    },
    {
        "text": "Quick sort picks a pivot and partitions the array into "
                "elements less than and greater than the pivot. Average case "
                "is O(n log n) but worst case is O(n^2) when the pivot is "
                "always the smallest or largest element.",
        "chapter": "Chapter 2", "filename": "lecture2_sorting.pdf", "page": 3
    },
    {
        "text": "Insertion sort builds the sorted array one element at a time. "
                "It is efficient for small arrays and nearly-sorted data. "
                "Time complexity is O(n^2) worst case but O(n) for nearly "
                "sorted input. It is stable and in-place.",
        "chapter": "Chapter 2", "filename": "lecture2_sorting.pdf", "page": 4
    },
    # Chapter 3
    {
        "text": "Recursion is when a function calls itself with a smaller "
                "subproblem. Every recursive function needs a base case to "
                "stop the recursion and a recursive case that moves toward "
                "the base case. Without a base case the function runs forever "
                "causing a stack overflow.",
        "chapter": "Chapter 3", "filename": "lecture3_recursion.pdf", "page": 1
    },
    {
        "text": "The call stack stores information about active function "
                "calls. Each recursive call adds a new frame to the stack. "
                "Deep recursion can cause stack overflow errors. The maximum "
                "recursion depth in Python is typically 1000. Tail recursion "
                "can sometimes be optimised by the compiler to avoid stack growth.",
        "chapter": "Chapter 3", "filename": "lecture3_recursion.pdf", "page": 2
    },
    {
        "text": "Classic recursive problems include factorial, Fibonacci, "
                "tower of Hanoi, and tree traversal. Naive recursive Fibonacci "
                "has O(2^n) time complexity due to repeated subproblems. "
                "Memoization improves this to O(n) by storing previously "
                "computed results.",
        "chapter": "Chapter 3", "filename": "lecture3_recursion.pdf", "page": 3
    },
    # Chapter 4
    {
        "text": "A stack is a Last-In-First-Out (LIFO) data structure. "
                "Elements are pushed onto the top and popped from the top. "
                "Push, pop, and peek are all O(1). Stacks are used in "
                "function call management, undo operations, expression "
                "evaluation, and depth-first search.",
        "chapter": "Chapter 4", "filename": "lecture4_stacks_queues.pdf", "page": 1
    },
    {
        "text": "A queue is a First-In-First-Out (FIFO) data structure. "
                "Elements are enqueued at the rear and dequeued from the front. "
                "All operations are O(1). Queues are used in breadth-first "
                "search, task scheduling, print spooling, and message passing.",
        "chapter": "Chapter 4", "filename": "lecture4_stacks_queues.pdf", "page": 2
    },
    {
        "text": "A priority queue dequeues elements based on priority rather "
                "than insertion order. It is typically implemented using a heap "
                "and supports O(log n) insertion and O(log n) extraction of "
                "the minimum or maximum element.",
        "chapter": "Chapter 4", "filename": "lecture4_stacks_queues.pdf", "page": 3
    },
    # Chapter 5
    {
        "text": "A graph consists of vertices and edges. Graphs can be "
                "directed or undirected, weighted or unweighted. Adjacency "
                "matrix uses O(V^2) space. Adjacency list uses O(V + E) space "
                "where V is vertices and E is edges.",
        "chapter": "Chapter 5", "filename": "lecture5_graphs.pdf", "page": 1
    },
    {
        "text": "Breadth-First Search (BFS) explores all neighbours of a node "
                "before moving to the next level. It uses a queue. BFS finds "
                "the shortest path in an unweighted graph. Time complexity is "
                "O(V + E). Nodes are visited level by level from the source.",
        "chapter": "Chapter 5", "filename": "lecture5_graphs.pdf", "page": 2
    },
    {
        "text": "Depth-First Search (DFS) explores as far as possible along "
                "each branch before backtracking. It uses a stack or recursion. "
                "DFS is used for cycle detection, topological sorting, and "
                "connected components. Time complexity is O(V + E).",
        "chapter": "Chapter 5", "filename": "lecture5_graphs.pdf", "page": 3
    },
    {
        "text": "The key difference between BFS and DFS is the data structure. "
                "BFS uses a queue (FIFO) and explores level by level. "
                "DFS uses a stack (LIFO) and goes deep before backtracking. "
                "BFS is better for shortest path. DFS uses less memory when "
                "the graph is wide.",
        "chapter": "Chapter 5", "filename": "lecture5_graphs.pdf", "page": 4
    },
    # Chapter 6
    {
        "text": "Dynamic programming solves problems by breaking them into "
                "overlapping subproblems and storing their solutions. It "
                "requires optimal substructure and overlapping subproblems. "
                "Without DP, redundant calculations lead to exponential time.",
        "chapter": "Chapter 6", "filename": "lecture6_dp.pdf", "page": 1
    },
    {
        "text": "Memoization is top-down dynamic programming. We solve "
                "recursively but cache subproblem results in a dictionary. "
                "Tabulation is bottom-up DP where we fill a table iteratively "
                "from smallest subproblems up to the final answer.",
        "chapter": "Chapter 6", "filename": "lecture6_dp.pdf", "page": 2
    },
    {
        "text": "The knapsack problem: given items with weights and values and "
                "a bag with capacity W, find the maximum value you can carry. "
                "The DP table has dimensions items x capacity. Time and space "
                "complexity are both O(n * W).",
        "chapter": "Chapter 6", "filename": "lecture6_dp.pdf", "page": 3
    },
    # Chapter 7
    {
        "text": "Greedy algorithms make the locally optimal choice at each step "
                "hoping to find the global optimum. They are simpler and faster "
                "than dynamic programming but do not always give the optimal "
                "solution. Greedy works when the problem has the greedy choice "
                "property and optimal substructure.",
        "chapter": "Chapter 7", "filename": "lecture7_greedy.pdf", "page": 1
    },
    {
        "text": "Dijkstra's algorithm finds shortest paths from a source to all "
                "vertices in a weighted graph with non-negative weights. It is "
                "a greedy algorithm that always picks the unvisited vertex with "
                "the smallest known distance. Time complexity is O((V+E) log V) "
                "with a priority queue.",
        "chapter": "Chapter 7", "filename": "lecture7_greedy.pdf", "page": 2
    },
]


def seed():
    print(f"\n{'='*50}")
    print(f"  Seeding Qdrant — collection: {COURSE_ID}")
    print(f"  Embed model   : {EMBED_MODEL}")
    print(f"  Chunks to insert: {len(TEST_CHUNKS)}")
    print(f"{'='*50}\n")

    # ── Connect to Qdrant ─────────────────────────────────────
    qdrant = QdrantClient(host=config.QDRANT_HOST, port=config.QDRANT_PORT)

    # ── Load embedding model ──────────────────────────────────
    print("Loading embedding model...")
    embedder = SentenceTransformer(EMBED_MODEL)
    test_vec = embedder.encode("test")
    vector_size = len(test_vec)
    print(f"Embedding model loaded. Vector size: {vector_size}")

    # ── Drop and recreate collection (clean slate) ────────────
    existing = [c.name for c in qdrant.get_collections().collections]
    if COURSE_ID in existing:
        print(f"Deleting existing collection '{COURSE_ID}'...")
        qdrant.delete_collection(COURSE_ID)

    print(f"Creating collection '{COURSE_ID}' with {vector_size}-dim vectors...")
    qdrant.create_collection(
        collection_name=COURSE_ID,
        vectors_config=VectorParams(
            size=vector_size,
            distance=Distance.COSINE
        )
    )

    # ── Embed and insert all chunks ───────────────────────────
    print("\nEmbedding and inserting chunks:")
    points = []

    for i, chunk in enumerate(TEST_CHUNKS):
        vector = embedder.encode(chunk["text"]).tolist()
        point  = PointStruct(
            id=str(uuid.uuid4()),
            vector=vector,
            payload={
                "text":     chunk["text"],
                "chapter":  chunk["chapter"],
                "filename": chunk["filename"],
                "page":     chunk["page"],
            }
        )
        points.append(point)
        print(f"  [{i+1:02d}/{len(TEST_CHUNKS)}] "
              f"{chunk['chapter']} — {chunk['filename']} p{chunk['page']} "
              f"| vector[0]={round(vector[0], 4)}")

    # ── Batch upsert ──────────────────────────────────────────
    print(f"\nUploading {len(points)} points to Qdrant...")
    qdrant.upsert(collection_name=COURSE_ID, points=points)

    # ── Verify ────────────────────────────────────────────────
    info = qdrant.get_collection(COURSE_ID)
    print(f"\n{'='*50}")
    print(f"  Verification")
    print(f"  Collection  : {COURSE_ID}")
    print(f"  Points stored: {info.points_count}")
    print(f"  Vector size : {info.config.params.vectors.size}")
    print(f"{'='*50}")

    # ── Quick search test ─────────────────────────────────────
    print("\nRunning test search: 'what is the difference between BFS and DFS'")
    query_vec = embedder.encode(
        "what is the difference between BFS and DFS"
    ).tolist()

    results = qdrant.query_points(
        collection_name=COURSE_ID,
        query=query_vec,
        limit=3
    )

    print("\nTop 3 vector search results:")
    for i, p in enumerate(results.points):
        print(f"\n  Result {i+1} (score: {round(p.score, 4)})")
        print(f"  Chapter : {p.payload['chapter']}")
        print(f"  File    : {p.payload['filename']} p{p.payload['page']}")
        print(f"  Text    : {p.payload['text'][:100]}...")

    print("\n\nSeeding complete. Run: streamlit run app.py")


if __name__ == "__main__":
    seed()