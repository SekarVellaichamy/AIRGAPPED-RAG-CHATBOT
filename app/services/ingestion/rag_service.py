
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from sqlmodel import Session, select
from sqlalchemy import text
from app.models.models import DocumentChunk, Document
from app.services.llm import get_llm_service
from pgvector.sqlalchemy import Vector

logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    """Structured result from RAG retrieval with metadata."""
    chunk: DocumentChunk
    score: float  # Similarity score (0-1, higher is better)
    document_name: str
    page_number: Optional[int]
    window_content: Optional[str] = None # Added for expanded context
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.window_content if self.window_content else self.chunk.content,
            "original_content": self.chunk.content,
            "score": self.score,
            "relevance_percent": round(self.score * 100, 1),
            "document_name": self.document_name,
            "page_number": self.page_number,
            "chunk_id": self.chunk.id
        }


class RAGService:
    def __init__(self):
        # Use the factory to get the configured LLM service (Ollama or vLLM)
        self.llm_service = get_llm_service()
        self.chunk_size = 500  # Characters
        self.chunk_overlap = 50
        # Relevance threshold: chunks with similarity below this are filtered out
        # Cosine similarity ranges from -1 to 1, but for normalized vectors it's typically 0-1
        self.min_relevance_threshold = 0.3
        self.window_size = 1 # Number of chunks before/after to fetch

    def split_text(self, text: str, use_semantic: bool = True) -> List[str]:
        """
        Split text into chunks. Uses Markdown-aware splitting by default.
        """
        from app.services.ingestion.chunker import MarkdownChunker
        
        # Use our new MarkdownChunker
        chunker = MarkdownChunker(chunk_size=self.chunk_size, chunk_overlap=self.chunk_overlap)
        return chunker.split_text(text)

    # Legacy splitting methods removed or deprecated in favor of MarkdownChunker

    
    def apply_mmr(
        self, 
        results: List[RetrievalResult], 
        lambda_param: float = 0.5,
        k: int = 5
    ) -> List[RetrievalResult]:
        """
        Apply Maximal Marginal Relevance (MMR) to diversify results.
        
        MMR balances relevance and diversity by penalizing documents
        that are similar to already-selected documents.
        
        Args:
            results: List of retrieval results with embeddings
            lambda_param: Balance between relevance (1.0) and diversity (0.0)
            k: Number of results to return
            
        Returns:
            Reordered results maximizing diversity
        """
        if len(results) <= 1:
            return results
        
        import numpy as np
        
        # Get embeddings for all results
        embeddings = []
        for r in results:
            if r.chunk.embedding:
                embeddings.append(np.array(r.chunk.embedding))
            else:
                # Fallback: can't compute MMR without embeddings
                return results[:k]
        
        embeddings = np.array(embeddings)
        
        # Compute similarity matrix
        def cosine_sim(a, b):
            norm_a = np.linalg.norm(a)
            norm_b = np.linalg.norm(b)
            if norm_a == 0 or norm_b == 0:
                return 0.0
            return np.dot(a, b) / (norm_a * norm_b)
        
        selected_indices = []
        remaining_indices = list(range(len(results)))
        
        # Select first result (highest relevance)
        best_idx = max(remaining_indices, key=lambda i: results[i].score)
        selected_indices.append(best_idx)
        remaining_indices.remove(best_idx)
        
        # Iteratively select remaining results
        while len(selected_indices) < k and remaining_indices:
            mmr_scores = []
            
            for idx in remaining_indices:
                # Relevance score (normalized)
                relevance = results[idx].score
                
                # Max similarity to any selected document
                max_sim = max(
                    cosine_sim(embeddings[idx], embeddings[sel_idx])
                    for sel_idx in selected_indices
                )
                
                # MMR score: balance relevance and diversity
                mmr = lambda_param * relevance - (1 - lambda_param) * max_sim
                mmr_scores.append((idx, mmr))
            
            # Select document with highest MMR score
            best_idx = max(mmr_scores, key=lambda x: x[1])[0]
            selected_indices.append(best_idx)
            remaining_indices.remove(best_idx)
        
        # Return results in MMR order
        return [results[i] for i in selected_indices]

    async def index_document(self, document_id: int, content: str, db_session: Session, use_agentic: bool = True):
        """
        Splits content into chunks, generates embeddings, and saves to DB.
        """
        logger.info(f"Indexing document {document_id} with length {len(content)}, agentic={use_agentic}")
        
        chunks_to_process = []
        
        if use_agentic:
            from app.services.ingestion.chunker import AgenticChunker
            chunker = AgenticChunker(self.llm_service, chunk_size=self.chunk_size, chunk_overlap=self.chunk_overlap)
            structural_chunks = chunker.split_and_summarize(content)
            
            # Flatten structure for processing but keep relationships
            for item in structural_chunks:
                # 1. Parent/Summary Chunk
                if item.get("is_summary"):
                    parent_text = item["content"]
                    parent_embedding = self._safe_get_embedding(parent_text)
                    if not parent_embedding: continue
                    
                    parent_chunk = DocumentChunk(
                        document_id=document_id,
                        content=parent_text,
                        embedding=parent_embedding,
                        is_summary=True,
                        parent_id=None
                    )
                    db_session.add(parent_chunk)
                    db_session.flush() # flush to get ID
                    
                    # 2. Child Chunks
                    for child_text in item["children"]:
                        chunks_to_process.append({
                            "text": child_text,
                            "parent_id": parent_chunk.id
                        })
                else:
                    # Non-propogated chunk (fallback)
                    # For items that didn't get summarized (too small), just treat as flat chunks
                    # But wait, AgenticChunker wraps even small stuff in a child list usually? 
                    # Our implementation of AgenticChunker puts small sections as single items with children=[]
                    # So we should check "content" 
                    text = item.get("content")
                    if text:
                        chunks_to_process.append({"text": text, "parent_id": None})
                    # And children if any (though logic says empty)
                    for child in item.get("children", []):
                         chunks_to_process.append({"text": child, "parent_id": None})
        else:
            # Legacy/Standard splitting
            raw_chunks = self.split_text(content)
            chunks_to_process = [{"text": t, "parent_id": None} for t in raw_chunks]
            
        logger.info(f"Processing {len(chunks_to_process)} detail chunks")
        
        for i, item in enumerate(chunks_to_process):
            chunk_text = item["text"].strip()
            parent_id = item["parent_id"]
            
            if not chunk_text:
                continue
                
            embedding = self._safe_get_embedding(chunk_text)
            if not embedding:
                logger.warning(f"Failed to get embedding for chunk {i}")
                continue
            
            doc_chunk = DocumentChunk(
                document_id=document_id,
                content=chunk_text,
                embedding=embedding,
                is_summary=False,
                parent_id=parent_id
            )
            db_session.add(doc_chunk)
                
        db_session.commit()
        logger.info(f"Finished indexing document {document_id}")

    def _safe_get_embedding(self, text: str) -> Optional[List[float]]:
        try:
            embedding = self.llm_service.get_embedding(text)
            if embedding and len(embedding) == 768:
                return embedding
            elif embedding:
                logger.warning(f"Embedding dimension mismatch: {len(embedding)}")
                return None
        except Exception as e:
            logger.error(f"Embedding error: {e}")
        return None

    def _fetch_window_context(self, chunk: DocumentChunk, db_session: Session) -> str:
        """
        Fetches context. 
        If chunk has a parent (hierarchical), returns Parent Summary + Chunk Content.
        Otherwise, fetches adjacent chunks (window).
        """
        try:
            # 1. Prefer Hierarchical Context
            logger.info(f"Fetching context for chunk {chunk.id}, parent_id={chunk.parent_id}")
            if chunk.parent_id:
                parent = db_session.get(DocumentChunk, chunk.parent_id)
                if parent:
                    return f"Context (Summary): {parent.content}\n\nDetail: {chunk.content}"
            
            # 2. Fallback to Window Context (Legacy)
            # We want chunks from the same document with IDs within window_size range
            start_id = chunk.id - self.window_size
            end_id = chunk.id + self.window_size
            
            stmt = select(DocumentChunk).where(
                DocumentChunk.document_id == chunk.document_id,
                DocumentChunk.id >= start_id,
                DocumentChunk.id <= end_id
            ).order_by(DocumentChunk.id)
            
            window_chunks = db_session.exec(stmt).all()
            
            # Combine content
            combined_content = "\n\n".join([c.content for c in window_chunks])
            return combined_content
            
        except Exception as e:
            logger.warning(f"Failed to fetch window context for chunk {chunk.id}: {e}")
            return chunk.content

    def retrieve_with_scores(
        self, 
        query: str, 
        db_session: Session, 
        k: int = 5,
        min_threshold: Optional[float] = None
    ) -> List[RetrievalResult]:
        """
        Embeds query and searches for similar chunks with relevance scores.
        Returns structured results including document metadata and similarity scores.
        Filters out chunks below the relevance threshold.
        """
        threshold = min_threshold if min_threshold is not None else self.min_relevance_threshold
        
        query_embedding = self.llm_service.get_embedding(query)
        if not query_embedding:
            logger.error("Could not generate embedding for query")
            return []
        
        try:
            # Use raw SQL to get both chunks and their cosine distance scores
            # Cosine distance = 1 - cosine_similarity, so we convert back
            # Note: Using CAST() instead of :: to avoid conflict with SQLAlchemy parameter syntax
            embedding_str = '[' + ','.join(map(str, query_embedding)) + ']'
            
            query_text = text("""
                SELECT 
                    dc.id,
                    dc.document_id,
                    dc.content,
                    dc.page_number,
                    dc.embedding,
                    d.filename,
                    1 - (dc.embedding <=> CAST(:query_embedding AS vector)) as similarity
                FROM documentchunk dc
                JOIN document d ON dc.document_id = d.id
                ORDER BY dc.embedding <=> CAST(:query_embedding AS vector)
                LIMIT :limit
            """)
            
            result = db_session.execute(
                query_text, 
                {"query_embedding": embedding_str, "limit": k * 2}  # Fetch more, then filter
            )
            
            retrieval_results = []
            for row in result:
                similarity = float(row.similarity)
                
                # Filter by threshold
                if similarity < threshold:
                    logger.debug(f"Filtering chunk {row.id} with score {similarity:.3f} (below threshold {threshold})")
                    continue
                
                # Fetch the actual DocumentChunk object
                chunk = db_session.get(DocumentChunk, row.id)
                if chunk:
                    # Fetch window context
                    window_content = self._fetch_window_context(chunk, db_session)
                    
                    retrieval_results.append(RetrievalResult(
                        chunk=chunk,
                        score=similarity,
                        document_name=row.filename,
                        page_number=row.page_number,
                        window_content=window_content
                    ))
                
                if len(retrieval_results) >= k:
                    break
            
            logger.info(f"Retrieved {len(retrieval_results)} chunks above threshold {threshold}")
            return retrieval_results
            
        except Exception as e:
            logger.error(f"Error during retrieval with scores: {e}")
            # Rollback to prevent transaction errors from propagating
            db_session.rollback()
            return []

    def retrieve(self, query: str, db_session: Session, k: int = 5) -> List[DocumentChunk]:
        """
        Legacy method: Embeds query and searches for similar chunks.
        Now uses retrieve_with_scores internally but returns only chunks for backward compatibility.
        """
        results = self.retrieve_with_scores(query, db_session, k)
        return [r.chunk for r in results]
    
    def calculate_confidence(self, results: List[RetrievalResult]) -> Dict[str, Any]:
        """
        Calculate overall confidence based on retrieval scores.
        Returns confidence level and average score.
        """
        if not results:
            return {"level": "none", "score": 0.0, "description": "No relevant documents found"}
        
        avg_score = sum(r.score for r in results) / len(results)
        top_score = max(r.score for r in results)
        
        if top_score >= 0.7:
            level = "high"
            description = "Highly relevant sources found"
        elif top_score >= 0.5:
            level = "medium"
            description = "Moderately relevant sources found"
        elif top_score >= 0.3:
            level = "low"
            description = "Limited relevant sources found"
        else:
            level = "none"
            description = "No strongly relevant sources"
        
        return {
            "level": level,
            "score": round(avg_score, 3),
            "top_score": round(top_score, 3),
            "description": description,
            "num_sources": len(results)
        }

    def hybrid_retrieve(
        self,
        query: str,
        db_session: Session,
        k: int = 5,
        min_threshold: Optional[float] = None,
        use_query_expansion: bool = False
    ) -> List[RetrievalResult]:
        """
        Hybrid retrieval combining vector search with BM25 keyword search.
        Uses Reciprocal Rank Fusion to combine results for better accuracy.
        
        Args:
            query: The search query
            db_session: Database session
            k: Number of results to return
            min_threshold: Minimum relevance threshold
            use_query_expansion: Whether to expand query with LLM
        """
        from app.services.ingestion.hybrid_search import HybridSearchService, reciprocal_rank_fusion
        
        threshold = min_threshold if min_threshold is not None else self.min_relevance_threshold
        
        # Optionally expand query for better recall
        search_queries = [query]
        if use_query_expansion:
            expanded = self._expand_query(query)
            if expanded:
                search_queries.extend(expanded)
                logger.info(f"Expanded query to {len(search_queries)} variants")
        
        # Step 1: Get vector search results
        query_embedding = self.llm_service.get_embedding(query)
        if not query_embedding:
            logger.error("Could not generate embedding for query")
            return []
        
        try:
            # Vector search with scores
            embedding_str = '[' + ','.join(map(str, query_embedding)) + ']'
            
            vector_query = text("""
                SELECT 
                    dc.id,
                    dc.document_id,
                    dc.content,
                    dc.page_number,
                    d.filename,
                    1 - (dc.embedding <=> CAST(:query_embedding AS vector)) as similarity
                FROM documentchunk dc
                JOIN document d ON dc.document_id = d.id
                ORDER BY dc.embedding <=> CAST(:query_embedding AS vector)
                LIMIT :limit
            """)
            
            vector_result = db_session.execute(
                vector_query,
                {"query_embedding": embedding_str, "limit": k * 3}
            )
            
            vector_results = []
            chunk_data = {}  # Cache chunk info
            
            for row in vector_result:
                chunk_id = row.id
                similarity = float(row.similarity)
                vector_results.append((chunk_id, similarity))
                chunk_data[chunk_id] = {
                    'id': chunk_id,
                    'content': row.content,
                    'document_id': row.document_id,
                    'document_name': row.filename,
                    'page_number': row.page_number
                }
            
            # Step 2: Get all chunks for BM25 (we need the full corpus)
            all_chunks_query = text("""
                SELECT dc.id, dc.content, dc.document_id, dc.page_number, d.filename
                FROM documentchunk dc
                JOIN document d ON dc.document_id = d.id
            """)
            all_chunks_result = db_session.execute(all_chunks_query)
            
            all_chunks = []
            for row in all_chunks_result:
                all_chunks.append({
                    'id': row.id,
                    'content': row.content,
                    'document_id': row.document_id,
                    'document_name': row.filename,
                    'page_number': row.page_number
                })
                if row.id not in chunk_data:
                    chunk_data[row.id] = {
                        'id': row.id,
                        'content': row.content,
                        'document_id': row.document_id,
                        'document_name': row.filename,
                        'page_number': row.page_number
                    }
            
            # Step 3: BM25 keyword search
            hybrid_service = HybridSearchService()
            hybrid_service.build_keyword_index(all_chunks)
            keyword_results = hybrid_service.keyword_search(query, k * 3)
            
            # Step 4: Combine using RRF
            combined = reciprocal_rank_fusion([vector_results, keyword_results])
            
            # Build final results
            retrieval_results = []
            vector_scores = {cid: score for cid, score in vector_results}
            keyword_scores = {cid: score for cid, score in keyword_results}
            max_kw = max((s for _, s in keyword_results), default=1.0) or 1.0
            
            for chunk_id, rrf_score in combined:
                vec_score = vector_scores.get(chunk_id, 0.0)
                kw_score = keyword_scores.get(chunk_id, 0.0) / max_kw if max_kw > 0 else 0
                
                # Use weighted combination for final score display
                final_score = 0.7 * vec_score + 0.3 * kw_score
                
                if final_score < threshold:
                    continue
                
                chunk_info = chunk_data.get(chunk_id)
                if chunk_info:
                    chunk = db_session.get(DocumentChunk, chunk_id)
                    if chunk:
                        retrieval_results.append(RetrievalResult(
                            chunk=chunk,
                            score=final_score,
                            document_name=chunk_info['document_name'],
                            page_number=chunk_info['page_number']
                        ))
                
                if len(retrieval_results) >= k:
                    break
            
            logger.info(f"Hybrid search retrieved {len(retrieval_results)} chunks (vector: {len(vector_results)}, keyword: {len(keyword_results)})")
            
            # Step 5: Apply MMR for diversity (retrieve more, then diversify)
            if len(retrieval_results) > k:
                retrieval_results = self.apply_mmr(retrieval_results, lambda_param=0.7, k=k)
                logger.info(f"Applied MMR, final results: {len(retrieval_results)}")
            
            return retrieval_results
            
        except Exception as e:
            logger.error(f"Error during hybrid retrieval: {e}")
            db_session.rollback()
            return []
    
    def _expand_query(self, query: str, max_expansions: int = 2) -> List[str]:
        """
        Use LLM to generate alternative phrasings of the query for better recall.
        """
        try:
            prompt = f"""Generate {max_expansions} alternative phrasings or related search queries for the following question. 
Return only the alternative queries, one per line, without numbering or explanations.

Original query: {query}

Alternative queries:"""
            
            messages = [{"role": "user", "content": prompt}]
            response = self.llm_service.generate_response(messages)
            
            if response:
                # Parse response into individual queries
                expansions = [line.strip() for line in response.strip().split('\n') if line.strip()]
                return expansions[:max_expansions]
        except Exception as e:
            logger.warning(f"Query expansion failed: {e}")
        
        return []
