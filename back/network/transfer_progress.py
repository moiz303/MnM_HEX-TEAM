#!/usr/bin/env python3
"""
Progress indicators for file transfer UX improvements
"""

import time

class TransferProgress:
    """Enhanced progress tracking for file transfers"""
    
    def __init__(self, total_chunks: int):
        self.total_chunks = total_chunks
        self.completed_chunks = 0
        self.failed_chunks = 0
        self.start_time = None
        self.bytes_transferred = 0
        self.total_bytes = 0
        
    def start(self, total_bytes: int):
        """Start tracking transfer progress"""
        self.start_time = time.time()
        self.total_bytes = total_bytes
        print(f"📁 Starting transfer: {self._format_bytes(total_bytes)}")
        
    def update_chunk(self, chunk_size: int, success: bool):
        """Update progress for a chunk"""
        if success:
            self.completed_chunks += 1
            self.bytes_transferred += chunk_size
        else:
            self.failed_chunks += 1
            
        self._print_progress()
        
    def _print_progress(self):
        """Print formatted progress information"""
        if not self.start_time:
            return
            
        elapsed = time.time() - self.start_time
        progress_percent = (self.completed_chunks / self.total_chunks) * 100
        
        # Calculate transfer speed
        if elapsed > 0:
            speed_bps = self.bytes_transferred / elapsed
            speed_str = self._format_speed(speed_bps)
        else:
            speed_str = "0 B/s"
            
        # Calculate ETA
        if progress_percent > 0 and speed_bps > 0:
            remaining_bytes = self.total_bytes - self.bytes_transferred
            eta_seconds = remaining_bytes / speed_bps if speed_bps > 0 else 0
            eta_str = self._format_time(eta_seconds)
        else:
            eta_str = "--:--"
            
        print(f"📊 Progress: {progress_percent:.1f}% | "
              f"🚀 {speed_str} | "
              f"⏱️ ETA: {eta_str} | "
              f"📦 {self.completed_chunks}/{self.total_chunks} chunks")
        
    def _format_bytes(self, bytes_count: int) -> str:
        """Format bytes in human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_count < 1024:
                return f"{bytes_count} {unit}"
            bytes_count /= 1024
        return f"{bytes_count:.1f} TB"
        
    def _format_speed(self, bps: float) -> str:
        """Format transfer speed"""
        if bps < 1024:
            return f"{bps:.1f} B/s"
        elif bps < 1024 * 1024:
            return f"{bps/1024:.1f} KB/s"
        elif bps < 1024 * 1024 * 1024:
            return f"{bps/(1024*1024):.1f} MB/s"
        else:
            return f"{bps/(1024*1024*1024):.1f} GB/s"
            
    def _format_time(self, seconds: float) -> str:
        """Format time duration"""
        if seconds < 60:
            return f"{seconds:.0f}s"
        elif seconds < 3600:
            return f"{seconds/60:.0f}m {seconds%60:.0f}s"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            secs = int(seconds % 60)
            return f"{hours}h {minutes}m {secs}s"
            
    def complete(self, success: bool):
        """Mark transfer as complete"""
        elapsed = time.time() - self.start_time if self.start_time else 0
        status = "✅ SUCCESS" if success else "❌ FAILED"
        
        print(f"\n🎯 Transfer {status}")
        print(f"📊 Final: {self.completed_chunks}/{self.total_chunks} chunks")
        print(f"📁 Size: {self._format_bytes(self.bytes_transferred)}")
        print(f"⏱️ Duration: {self._format_time(elapsed)}")
        
        if elapsed > 0:
            avg_speed = self.bytes_transferred / elapsed
            print(f"🚀 Average: {self._format_speed(avg_speed)}")


if __name__ == "__main__":
    # Test progress tracking
    import time
    
    progress = TransferProgress(10)
    progress.start(1024 * 1024)  # 1MB
    
    # Simulate chunk updates
    for i in range(10):
        chunk_size = 1024 * 100  # 100KB chunks
        progress.update_chunk(chunk_size, True)
        time.sleep(0.5)
    
    progress.complete(True)
