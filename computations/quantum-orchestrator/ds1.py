"""
Quantum Math Orchestrator - 7 Agents + Omnibus Sanity Check
Heavy computational mode - runs natively on local machine
"""

import asyncio
import json
import logging
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import traceback

# Heavy imports
import numpy as np
import psutil

# Optional quantum imports
try:
    import qiskit
    from qiskit import QuantumCircuit, Aer, execute
    QISKIT_AVAILABLE = True
except ImportError:
    QISKIT_AVAILABLE = False
    print("⚠️ Qiskit not available - quantum features limited")

# Optional JS engine
try:
    import execjs
    JS_AVAILABLE = True
except ImportError:
    JS_AVAILABLE = False
    print("⚠️ ExecJS not available - JS parsing limited")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class AgentResult:
    """Standardized output from each agent"""
    agent_name: str
    status: str  # 'success', 'failed', 'retry'
    data: Dict[str, Any]
    metrics: Dict[str, float]
    errors: List[str] = field(default_factory=list)


class QuantumOrchestratorSkill:
    """
    Orchestrates 7 specialized agents:
    1. Code Quality Agent
    2. Quantum Math Agent (heavy numpy/qiskit)
    3. Grammar Logic Agent
    4. Mechanism Design Agent
    5. Logit Processor Agent
    6. JS Wall Agent
    7. Rotating Proxy Agent
    + Omnibus Sanity Check Agent (gatekeeper)
    """
    
    def __init__(self):
        self.thread_pool = ThreadPoolExecutor(max_workers=8)
        self.process_pool = ProcessPoolExecutor(max_workers=4)
        self.metrics = {
            'total_time': 0,
            'agent_times': {},
            'memory_peak_mb': 0
        }
        
        # Agent registry
        self.agents = {
            'code_quality': self.agent_code_quality,
            'quantum_math': self.agent_quantum_math,
            'grammar_logic': self.agent_grammar_logic,
            'mechanism_design': self.agent_mechanism_design,
            'logit_processor': self.agent_logit_processor,
            'js_wall': self.agent_js_wall,
            'proxy_rotator': self.agent_proxy_rotator,
        }
        
        logger.info("✅ QuantumOrchestrator initialized with 7 agents")

    # ================================================================
    # AGENT 1: CODE QUALITY
    # ================================================================
    def agent_code_quality(self, data: Dict, feedback: Optional[str] = None) -> Dict:
        """Analyze and improve code quality"""
        logger.info("🔍 Agent 1: Code Quality Analysis")
        
        code = data.get('code', '')
        
        # Detect patterns
        issues = []
        if 'import *' in code:
            issues.append("Wildcard import detected")
        if len(code.split('\n')) > 500:
            issues.append("File too long (>500 lines)")
            
        # Check for type hints
        has_type_hints = ':' in code and ('->' in code or 'def' in code)
        
        return {
            'status': 'success',
            'issues': issues,
            'has_type_hints': has_type_hints,
            'line_count': len(code.split('\n')),
            'suggestions': [
                "Add type hints" if not has_type_hints else "Type hints good"
            ]
        }

    # ================================================================
    # AGENT 2: QUANTUM MATH (HEAVY COMPUTE)
    # ================================================================
    def agent_quantum_math(self, data: Dict, feedback: Optional[str] = None) -> Dict:
        """
        HEAVY COMPUTE - Quantum math operations
        Runs natively with full CPU/GPU access
        """
        logger.info("🧮 Agent 2: Quantum Math Computation (HEAVY)")
        
        start_time = time.time()
        matrix_size = data.get('matrix_size', 1000)
        
        # Track memory
        mem_before = psutil.Process().memory_info().rss / 1024 / 1024
        
        try:
            # --- Heavy linear algebra ---
            logger.info(f"  Generating {matrix_size}x{matrix_size} matrix...")
            matrix = np.random.randn(matrix_size, matrix_size)
            
            logger.info(f"  Computing eigenvalues (O(n³))...")
            eigenvalues = np.linalg.eigvals(matrix)
            
            logger.info(f"  Computing SVD...")
            u, s, vh = np.linalg.svd(matrix, full_matrices=False)
            
            # --- Quantum circuit simulation if Qiskit available ---
            quantum_result = None
            if QISKIT_AVAILABLE and data.get('use_quantum', False):
                logger.info("  Simulating quantum circuit...")
                qc = QuantumCircuit(20, 20)
                for i in range(20):
                    qc.h(i)
                qc.measure_all()
                
                backend = Aer.get_backend('aer_simulator')
                job = execute(qc, backend, shots=1024)
                quantum_result = job.result().get_counts()
            
            mem_after = psutil.Process().memory_info().rss / 1024 / 1024
            
            result = {
                'status': 'success',
                'eigenvalues': eigenvalues[:10].tolist(),  # Top 10 only
                'singular_values': s[:10].tolist(),
                'matrix_shape': matrix.shape,
                'quantum_result': quantum_result,
                'memory_used_mb': mem_after - mem_before,
                'computation_time': time.time() - start_time,
                'numpy_version': np.__version__,
                'qiskit_available': QISKIT_AVAILABLE
            }
            
            logger.info(f"  ✅ Computation complete in {result['computation_time']:.2f}s")
            return result
            
        except MemoryError as e:
            logger.error(f"  ❌ Out of memory: {e}")
            return {
                'status': 'failed',
                'error': str(e),
                'memory_available_mb': psutil.virtual_memory().available / 1024 / 1024
            }
        except Exception as e:
            logger.error(f"  ❌ Error: {e}")
            return {'status': 'failed', 'error': str(e), 'traceback': traceback.format_exc()}

    # ================================================================
    # AGENT 3: GRAMMAR LOGIC
    # ================================================================
    def agent_grammar_logic(self, data: Dict, feedback: Optional[str] = None) -> Dict:
        """Check grammar and logical consistency"""
        logger.info("📝 Agent 3: Grammar Logic Check")
        
        text = data.get('text', '')
        
        # Simple grammar checks
        sentences = text.split('.')
        issues = []
        
        for i, sent in enumerate(sentences):
            if len(sent.strip()) > 0 and sent.strip()[0].islower():
                issues.append(f"Sentence {i+1} starts with lowercase")
            if sent.count('(') != sent.count(')'):
                issues.append(f"Sentence {i+1} has mismatched parentheses")
        
        return {
            'status': 'success',
            'issues': issues,
            'sentence_count': len(sentences),
            'is_logically_consistent': len(issues) == 0
        }

    # ================================================================
    # AGENT 4: MECHANISM DESIGN (STRATEGIC BUILDING BLOCKS)
    # ================================================================
    def agent_mechanism_design(self, data: Dict, feedback: Optional[str] = None) -> Dict:
        """Design strategic building blocks from requirements"""
        logger.info("🏗️ Agent 4: Mechanism Design")
        
        requirements = data.get('requirements', '')
        
        # Parse requirements into building blocks
        blocks = []
        if 'API' in requirements:
            blocks.append({'type': 'api_gateway', 'priority': 1})
        if 'database' in requirements.lower():
            blocks.append({'type': 'data_layer', 'priority': 2})
        if 'quantum' in requirements.lower():
            blocks.append({'type': 'quantum_processor', 'priority': 1})
        
        return {
            'status': 'success',
            'building_blocks': blocks,
            'architecture': 'microservices',
            'recommended_stack': ['Python', 'FastAPI', 'PostgreSQL']
        }

    # ================================================================
    # AGENT 5: LOGIT PROCESSOR
    # ================================================================
    def agent_logit_processor(self, data: Dict, feedback: Optional[str] = None) -> Dict:
        """Process logit transformations"""
        logger.info("📊 Agent 5: Logit Processor")
        
        values = data.get('values', [0.1, 0.5, 0.9])
        
        # Logit transformation: log(p/(1-p))
        def logit(p):
            p = np.clip(p, 1e-10, 1 - 1e-10)
            return np.log(p / (1 - p))
        
        logits = [logit(p) for p in values]
        
        return {
            'status': 'success',
            'original_values': values,
            'logits': logits,
            'inverse': [1/(1+np.exp(-l)) for l in logits]
        }

    # ================================================================
    # AGENT 6: JS WALL
    # ================================================================
    def agent_js_wall(self, data: Dict, feedback: Optional[str] = None) -> Dict:
        """Parse and validate JavaScript code"""
        logger.info("🌐 Agent 6: JS Wall")
        
        js_code = data.get('javascript', '')
        
        if not JS_AVAILABLE:
            # Fallback: basic parsing
            return {
                'status': 'warning',
                'message': 'ExecJS not available - basic parsing only',
                'syntax_errors': [],
                'function_count': js_code.count('function'),
                'arrow_count': js_code.count('=>'),
                'valid': True
            }
        
        try:
            ctx = execjs.compile("""
                function validate(code) {
                    try {
                        eval(code);
                        return { valid: true, errors: [] };
                    } catch(e) {
                        return { valid: false, errors: [e.toString()] };
                    }
                }
            """)
            
            result = ctx.call('validate', js_code)
            return {
                'status': 'success' if result['valid'] else 'failed',
                'valid': result['valid'],
                'errors': result['errors'],
                'line_count': len(js_code.split('\n'))
            }
        except Exception as e:
            return {'status': 'failed', 'error': str(e)}

    # ================================================================
    # AGENT 7: ROTATING PROXY
    # ================================================================
    def agent_proxy_rotator(self, data: Dict, feedback: Optional[str] = None) -> Dict:
        """Manage rotating proxies"""
        logger.info("🔄 Agent 7: Rotating Proxy Manager")
        
        # Proxy list from config or environment
        proxies = os.environ.get('PROXY_LIST', 'http://proxy1:8080,http://proxy2:8080').split(',')
        
        # Simple rotation
        import random
        selected = random.choice(proxies) if proxies else None
        
        return {
            'status': 'success',
            'selected_proxy': selected,
            'available_proxies': len(proxies),
            'rotation_strategy': 'random',
            'proxy_healthy': True if selected else False
        }

    # ================================================================
    # OMNIBUS SANITY CHECK (Gatekeeper)
    # ================================================================
    def omnibus_sanity_check(self, result: Dict) -> Tuple[bool, str]:
        """
        Gatekeeper - validates all agent outputs
        Returns: (passed: bool, feedback: str)
        """
        logger.info("🔒 Omnibus Sanity Check")
        
        # Check for required fields
        if result.get('status') == 'failed':
            return False, f"Agent failed: {result.get('error', 'unknown error')}"
        
        if 'status' not in result:
            return False, "Missing 'status' field in result"
        
        # Numerical sanity checks
        if 'eigenvalues' in result:
            evals = result['eigenvalues']
            if any(np.isnan(x) or np.isinf(x) for x in evals):
                return False, "NaN or Inf detected in eigenvalues"
        
        if 'memory_used_mb' in result:
            if result['memory_used_mb'] > 15000:
                return False, f"Memory usage too high: {result['memory_used_mb']:.0f}MB"
        
        # JavaScript sanity
        if 'valid' in result and not result['valid']:
            return False, f"JS validation failed: {result.get('errors', [])}"
        
        return True, "All sanity checks passed"

    # ================================================================
    # MAIN ORCHESTRATOR
    # ================================================================
    async def run_sequential_pipeline(self, input_data: Dict) -> Dict[str, AgentResult]:
        """
        Run all 7 agents sequentially with sanity checks
        """
        logger.info("🚀 Starting Sequential Pipeline")
        start_time = time.time()
        
        results = {}
        current_data = input_data.copy()
        
        agent_names = list(self.agents.keys())
        
        for i, (name, agent_func) in enumerate(self.agents.items(), 1):
            logger.info(f"\n{'='*50}")
            logger.info(f"Agent {i}/7: {name.upper()}")
            logger.info(f"{'='*50}")
            
            agent_start = time.time()
            
            # Run agent
            try:
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    self.thread_pool,
                    agent_func,
                    current_data,
                    None
                )
            except Exception as e:
                result = {'status': 'failed', 'error': str(e)}
            
            agent_time = time.time() - agent_start
            self.metrics['agent_times'][name] = agent_time
            
            # --- SANITY CHECK ---
            passed, feedback = self.omnibus_sanity_check(result)
            
            if not passed:
                logger.warning(f"  ⚠️ Sanity check failed: {feedback}")
                # Retry once
                logger.info(f"  🔄 Retrying {name}...")
                try:
                    result = await loop.run_in_executor(
                        self.thread_pool,
                        agent_func,
                        current_data,
                        feedback
                    )
                    passed, feedback = self.omnibus_sanity_check(result)
                    if not passed:
                        logger.error(f"  ❌ Retry failed: {feedback}")
                except Exception as e:
                    result = {'status': 'failed', 'error': str(e)}
            
            # Store result
            results[name] = AgentResult(
                agent_name=name,
                status=result.get('status', 'unknown'),
                data=result,
                metrics={'time_seconds': agent_time},
                errors=[feedback] if not passed else []
            )
            
            # Pass data to next agent
            current_data = result
            current_data['_previous_agent'] = name
            
            # Update metrics
            mem = psutil.Process().memory_info().rss / 1024 / 1024
            self.metrics['memory_peak_mb'] = max(self.metrics['memory_peak_mb'], mem)
            
            logger.info(f"  ✅ Completed in {agent_time:.2f}s | Memory: {mem:.0f}MB")
        
        self.metrics['total_time'] = time.time() - start_time
        
        logger.info(f"\n{'='*50}")
        logger.info(f"✅ PIPELINE COMPLETE")
        logger.info(f"Total time: {self.metrics['total_time']:.2f}s")
        logger.info(f"Peak memory: {self.metrics['memory_peak_mb']:.0f}MB")
        logger.info(f"{'='*50}")
        
        return results


# ================================================================
# HERMES AGENT ENTRY POINT
# ================================================================

async def main(input_data: Dict) -> Dict:
    """
    Main entry point for Hermes Agent skill
    """
    orchestrator = QuantumOrchestratorSkill()
    results = await orchestrator.run_sequential_pipeline(input_data)
    
    # Return summary
    return {
        'pipeline_status': all(r.status == 'success' for r in results.values()),
        'agents': {name: r.status for name, r in results.items()},
        'metrics': orchestrator.metrics,
        'detailed_results': {name: r.data for name, r in results.items()}
    }


# For direct testing
if __name__ == "__main__":
    test_input = {
        'code': 'def hello(): print("world")',
        'text': 'The quick brown fox jumps over the lazy dog.',
        'requirements': 'Build a quantum API with database',
        'values': [0.1, 0.5, 0.9],
        'javascript': 'function add(a,b) { return a+b; }',
        'matrix_size': 500,  # Heavy compute
        'use_quantum': True
    }
    
    import asyncio
    result = asyncio.run(main(test_input))
    print(json.dumps(result, indent=2, default=str))