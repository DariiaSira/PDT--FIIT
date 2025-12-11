## Assignment: MongoDB Data Model for an Instagram / Twitter Lite Social Network

Design a MongoDB data model for a lightweight social network similar to Instagram or Twitter, enabling content publishing and social interactions.

---

## Tasks

1. **Design a data model using at least 3 different MongoDB design patterns**  
   (e.g., Subset Pattern, Polymorphic Pattern, Outlier Pattern, Bucket Pattern, …).

2. **Explain your design:**  
   - Which fields and entities will be embedded, and which will be referenced?  
   - Justify each decision.  
   - Justify the selection of design patterns used.

3. **Provide JSON-like examples** for your proposed document structures, e.g.:

```json
{
  "_id": ObjectId,
  "username": "string",
  ...
}
```

## Main Entities in the System

```
**Users**
- Profile, basic information, settings  
- Follower / following counters  
- Activity history  

**Posts**
- Various content types (text, image, video, external link)  
- Metadata (timestamp, author, tags, location)  

**Comments**
- Short textual reactions from users  
- Popular posts may accumulate thousands of comments  

**Likes / Reactions**
- User reactions to a post or a comment  

**Follows**
- Information about who follows whom  
```

## Typical User Scenarios and Interactions

```
**1. User Feed (main screen)** — ~35% of all queries  
When the user opens the application, the system must quickly load:
- Latest posts from followed users  
- Basic metadata about authors (avatar, username)  
- A small sample of comments (e.g., 3 newest)  
- Like and reaction counts  

**2. Post Detail View** — ~20% of queries  
Displays:
- Paginated comments  
- All reactions  
- Full profile details of the post's author  

**3. Reacting to a Post or Comment** — ~15% of queries  
Likes and other reactions.  
These operations are very frequent and must be extremely fast and easily scalable.

**4. Adding a New Comment** — ~10% of queries  
When a user adds a comment:
- A new document is created in the *comments* collection  
- Comment counters in **Posts** are updated  
- Embedded comment previews inside the post are updated  
  (if using the Subset Pattern)  

**5. Publishing a New Post** — ~5% of queries  
When a user shares new text/image/video:
- A new post document is inserted  
- The author's *post count* is updated  

This is relatively infrequent compared to feed queries.

**6. Viewing a User Profile** — ~8% of queries  
The system loads:
- Basic user information  
- Recent posts by the author  
- Counters (followers, following, posts)  

These queries are common but less heavy than the feed.

**7. Follow / Unfollow** — <5%  
Creating or deleting a follow relationship and updating counters.

**8. Searching Users or Hashtags** — <5%  
Full-text and autocomplete queries.
```

---
## Implementation

The first key step is analyzing the user scenarios and their frequency. The system workload is dominated by read-heavy operations: the user feed (~35%), post detail view (~20%), and profile view (~8%). These scenarios require loading recent posts, author metadata, small comment samples, full comment threads, reactions, and profile details. Write-intensive operations include reactions (~15%) and adding comments (~10%), which generate frequent and lightweight inserts or updates. Less frequent actions include publishing new posts (~5%), follow/unfollow operations (<5%), and search queries (<5%). This model applies three MongoDB design patterns: the Subset Pattern (comment previews embedded in posts), the Polymorphic Pattern (a unified reactions collection for multiple target types), and the Bucket Pattern (time-based user activity buckets).

From this distribution, the most critical requirement for the data model is minimizing the number of queries for feed and post-detail retrieval, ensuring these views load quickly. At the same time, high-frequency write operations such as likes and comments must be scalable and efficient, often implemented through separate collections with counters maintained in post documents. This leads to a design where read paths (feed and detail) are optimized via embedding and precomputed aggregates, while write paths (reactions, comments) are handled through lightweight, append-only operations.

The second step focuses on defining the necessary collections and their relationships. The core collections are: users, posts, comments, reactions (likes and other types), follows, and optionally activities or user_activity for tracking user actions. At this stage, without considering embedding, we determine the referencing structure: each post should store a reference to its author (user); each comment must reference both the post it belongs to and the user who created it; reactions should be generic, containing a reference to the user and either a post or a comment; and the follows collection should store pairs of followerUserId → followedUserId. Together with user-level follower/following counters, the follows collection supports efficient feed generation based on the list of authors a user follows.

This model applies three MongoDB design patterns: the Subset Pattern (comment previews in posts), the Polymorphic Pattern (unified reactions collection), and the Bucket Pattern (time‑based user activity buckets).

In the users collection, we store the full user profile as a standalone document: identifier, username, avatar, bio, settings, follower/following/post counters, and, if needed, aggregated activity history. This provides a stable single source of truth that all other collections can reference, which is especially important for profile view and author details in the post detail screen. In the remaining entities, we do not embed the full profile; instead, we embed only small, frequently used fragments—such as the author’s username and avatar inside posts and comments. When the interface requires full profile information (e.g., the profile screen or detailed post view), the system follows the authorId reference back to the users collection, allowing the profile to be updated in one place without duplicating large amounts of data across the database. The optional activityBuckets field in the user-related activity collection is where the Bucket Pattern is applied, grouping many small events into time-based buckets.

In the posts collection, we intentionally combine embedding and referencing to optimize the most frequent queries—loading the feed and the post detail view. Each post embeds a small “snapshot” of the author (id, username, avatar), allowing the feed to render post cards without querying users again. The post document also stores aggregates like likesCount and commentsCount, avoiding expensive recalculations based on reactions or comments, which is crucial under high read load. All comments live as separate documents in the comments collection and reference their post via postId and their author via authorId, which supports thousands of comments per post and efficient pagination. A key element here is the Subset Pattern for comments: each post embeds only a small subset (e.g., the 2–3 most recent comments) as a lightweight preview. This enables the feed to quickly show a short discussion snippet without joining the full comments collection, while the full detail view fetches the complete comment thread with pagination directly from comments.

For reactions, we use the Polymorphic Pattern so that a single structure supports reactions on both posts and comments. Instead of maintaining two collections (postLikes and commentLikes), we create one reactions collection where each document stores userId, reaction type (like, love, etc.), and a targetType + targetId pair. targetType specifies whether the reaction belongs to a post or a comment, and targetId identifies the specific document. This unified approach simplifies code and scaling: one collection, shared indexes, and consistent write logic for the most frequent write operations (likes and other reactions). At the same time, posts and comments store only aggregated like and reaction counts—not the reaction documents themselves—ensuring that high‑traffic read paths (especially the feed) remain fast and predictable. For comments we apply the same principle as for posts: the raw reaction documents are stored only in the reactions collection, while comments maintain just their aggregated reactionsCount field.

As the third pattern, we use the Bucket Pattern for user activity history: rather than storing millions of individual events (each like, comment, or post) as separate documents, we group them into time‑based buckets, such as monthly activity per user. Each bucket contains an array of actions for a given (userId, month), reducing the number of documents, improving analytical and history queries, and demonstrating advanced MongoDB data‑modeling practices. Follow relationships are kept in a dedicated follows collection using simple references between users (followerId and followedId), while users also maintain follower/following counters; this design makes follow/unfollow updates cheap and supports efficient feed generation based on the list of followed users.

So, JSON examples are below:

**Users**
```
{
  _id: ObjectId,
  username: string,
  email: string,
  passwordHash: string,
  avatarUrl: string,
  bio: string,
  settings: {
    language: string,
    isPrivate: bool,
    notifications: {
      likes: bool,
      comments: bool,
      follows: bool
    }
  },
  followersCount: int,
  followingCount: int,
  postsCount: int
}
```

**Posts (embed author snapshot + subset comments)**
```
{
  _id: ObjectId,
  authorId: ObjectId,          // ref -> users
  author: {                    // embed subset user (Subset pattern)
    _id: ObjectId,
    username: string,
    avatarUrl: string
  },
  contentType: string,         // "text" | "image" | "video" | "link"
  text: string,
  mediaUrl: string | null,
  externalLink: string | null,
  tags: [string],
  location: {
    name: string,
    lat: number,
    lon: number
  } | null,
  createdAt: Date,
  likesCount: int,
  reactionsCount: int,
  commentsCount: int,
  commentsPreview: [           // Subset pattern
    {
      _id: ObjectId,           // ref -> comments
      authorId: ObjectId,
      authorUsername: string,
      text: string,
      createdAt: Date
    }
  ]
}
```

**Comments**
```
{
  _id: ObjectId,
  postId: ObjectId,            // ref -> posts
  authorId: ObjectId,          // ref -> users
  text: string,
  createdAt: Date,
  reactionsCount: int
}
```

**Reactions (Polymorphic pattern)**
```
{
  _id: ObjectId,
  userId: ObjectId,            // ref -> users
  targetType: string,          // "post" | "comment"
  targetId: ObjectId,          // ref -> posts OR comments
  reactionType: string,        // "like" | "love" | ...
  createdAt: Date
}
```

**Follows**
```
{
  _id: ObjectId,
  followerId: ObjectId,        // ref -> users
  followedId: ObjectId,        // ref -> users
  createdAt: Date
}
```

**User_activity (Bucket pattern, optional)**
```
{
  _id: ObjectId,
  userId: ObjectId,            // ref -> users
  period: string,              // "YYYY-MM"
  actions: [
    {
      type: string,            // "post" | "comment" | "like"
      targetId: ObjectId,      // ref -> posts/comments
      createdAt: Date
    }
  ]
}
```

