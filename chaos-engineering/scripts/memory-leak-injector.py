#!/usr/bin/env python3
"""
Memory Leak Injector
Simulates a memory leak in a pod by gradually consuming memory
"""

import os
import sys
import time
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


class MemoryLeakSimulator:
    """Simulates a gradual memory leak"""
    
    def __init__(
        self,
        leak_rate_mb: float = 10.0,
        interval_seconds: int = 60,
        max_memory_mb: float = 500.0
    ):
        self.leak_rate_mb = leak_rate_mb
        self.interval_seconds = interval_seconds
        self.max_memory_mb = max_memory_mb
        self.leaked_memory = []
        self.current_memory_mb = 0
        
        logger.info(f"Memory leak simulator initialized:")
        logger.info(f"  Leak rate: {leak_rate_mb} MB every {interval_seconds} seconds")
        logger.info(f"  Max memory: {max_memory_mb} MB")
    
    def start(self):
        """Start leaking memory"""
        
        logger.info("Starting memory leak simulation...")
        
        try:
            while self.current_memory_mb < self.max_memory_mb:
                # Allocate memory
                chunk_size = int(self.leak_rate_mb * 1024 * 1024)  # Convert MB to bytes
                memory_chunk = bytearray(chunk_size)
                
                # Fill with data to ensure it's actually allocated
                for i in range(0, len(memory_chunk), 4096):
                    memory_chunk[i] = 1
                
                self.leaked_memory.append(memory_chunk)
                self.current_memory_mb += self.leak_rate_mb
                
                logger.info(f"Memory leaked: {self.current_memory_mb:.2f} MB / {self.max_memory_mb} MB")
                
                # Wait before next leak
                time.sleep(self.interval_seconds)
            
            logger.warning(f"Maximum memory ({self.max_memory_mb} MB) reached!")
            logger.info("Holding memory to trigger OOMKill...")
            
            # Hold the memory indefinitely
            while True:
                time.sleep(10)
                logger.info(f"Still holding {self.current_memory_mb:.2f} MB")
                
        except KeyboardInterrupt:
            logger.info("Memory leak simulation interrupted")
        except Exception as e:
            logger.error(f"Error during simulation: {e}", exc_info=True)
            sys.exit(1)


def main():
    """Main entry point"""
    
    # Configuration from environment variables
    leak_rate_mb = float(os.getenv('LEAK_RATE_MB', '10'))
    interval_seconds = int(os.getenv('INTERVAL_SECONDS', '60'))
    max_memory_mb = float(os.getenv('MAX_MEMORY_MB', '500'))
    
    simulator = MemoryLeakSimulator(
        leak_rate_mb=leak_rate_mb,
        interval_seconds=interval_seconds,
        max_memory_mb=max_memory_mb
    )
    
    simulator.start()


if __name__ == "__main__":
    main()
