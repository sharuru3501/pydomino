"""
Per-Track Audio Router
Routes MIDI notes to different audio sources based on track assignment
"""
import os
from typing import Dict, Optional, List, Any
from dataclasses import dataclass
from PySide6.QtCore import QObject, Signal

from src.midi_data_model import MidiNote
from src.audio_source_manager import AudioSource, AudioSourceType, get_audio_source_manager
from src.audio_system import get_audio_manager
from src.midi_routing import get_midi_routing_manager

try:
    import fluidsynth
    FLUIDSYNTH_AVAILABLE = True
except ImportError:
    FLUIDSYNTH_AVAILABLE = False

try:
    import rtmidi
    RTMIDI_AVAILABLE = True
except ImportError:
    RTMIDI_AVAILABLE = False

@dataclass
class TrackAudioInstance:
    """Represents an audio instance for a specific track"""
    track_index: int
    source: AudioSource
    fluidsynth_instance: Optional[Any] = None  # FluidSynth instance for soundfonts
    midi_out_port: Optional[Any] = None  # MIDI output port for external devices
    soundfont_id: Optional[int] = None  # Soundfont ID in FluidSynth

class PerTrackAudioRouter(QObject):
    """
    Routes audio for each track to its assigned audio source
    """
    
    # Signals
    routing_error = Signal(str, str)  # track_name, error_message
    routing_success = Signal(str, str)  # track_name, source_name
    
    def __init__(self):
        super().__init__()
        
        # Track audio instances
        self.track_instances: Dict[int, TrackAudioInstance] = {}
        
        # External MIDI output ports
        self.midi_out_ports: Dict[str, Any] = {}  # port_name -> rtmidi.MidiOut
        
        # Manager references (will be set during initialization)
        self.audio_source_manager = None
        self.audio_manager = None
        self.midi_routing_manager = None
    
    def _update_manager_references(self):
        """Update manager references (called during initialization)"""
        self.audio_source_manager = get_audio_source_manager()
        self.audio_manager = get_audio_manager()
        self.midi_routing_manager = get_midi_routing_manager()
        print(f"PerTrackRouter: Updated manager references - ASM: {self.audio_source_manager is not None}, AM: {self.audio_manager is not None}, MRM: {self.midi_routing_manager is not None}")
    
    def initialize_track_audio(self, track_index: int) -> bool:
        """Initialize audio for a specific track based on its assigned source"""
        print(f"PerTrackRouter: Initializing track {track_index}...")
        
        # Update manager references if needed
        if not self.audio_source_manager:
            self._update_manager_references()
        
        if not self.audio_source_manager:
            print(f"PerTrackRouter: No audio source manager available for track {track_index}")
            return False
        
        # Get assigned audio source
        source = self.audio_source_manager.get_track_source(track_index)
        if not source:
            print(f"PerTrackRouter: No audio source assigned to track {track_index}")
            return False
        
        print(f"PerTrackRouter: Track {track_index} source: {source.name} (type: {source.source_type}, ch: {source.channel}, prog: {source.program})")
        
        # Clean up existing instance
        self.cleanup_track_audio(track_index)
        
        success = False
        
        if source.source_type == AudioSourceType.SOUNDFONT:
            success = self._initialize_soundfont_audio(track_index, source)
        elif source.source_type == AudioSourceType.EXTERNAL_MIDI:
            success = self._initialize_external_midi(track_index, source)
        elif source.name.startswith("internal_fluidsynth_ch"):
            # Handle channel-specific internal FluidSynth assignments
            success = self._initialize_internal_fluidsynth(track_index, source)
        
        if success:
            print(f"Track {track_index} audio initialized: {source.name}")
            self.routing_success.emit(f"Track{track_index:02d}", source.name)
        else:
            print(f"Failed to initialize audio for track {track_index}: {source.name}")
            self.routing_error.emit(f"Track{track_index:02d}", f"Failed to initialize {source.name}")
        
        return success
    
    def _initialize_soundfont_audio(self, track_index: int, source: AudioSource) -> bool:
        """Initialize a dedicated FluidSynth instance for a soundfont"""
        if not FLUIDSYNTH_AVAILABLE:
            print("FluidSynth not available for soundfont audio")
            return False
        
        if not source.file_path or not os.path.exists(source.file_path):
            print(f"Soundfont file not found: {source.file_path}")
            return False
        
        try:
            # Import AudioSettings to use same settings as shared instance
            from src.audio_system import AudioSettings
            
            # Create new FluidSynth instance with same settings as shared instance
            default_settings = AudioSettings()
            fs = fluidsynth.Synth(
                samplerate=default_settings.sample_rate,  # 44100Hz
                gain=0.0  # Start with zero gain to prevent startup pops
            )
            fs.start(driver="coreaudio")  # Use CoreAudio on macOS
            
            # Load soundfont
            soundfont_id = fs.sfload(source.file_path)
            if soundfont_id == -1:
                print(f"Failed to load soundfont: {source.file_path}")
                fs.delete()
                return False
            
            # Select program for this track (use program 0 = piano as fallback)
            program_number = max(0, min(127, source.program - 1))  # Ensure valid range 0-127
            fs.program_select(source.channel, soundfont_id, 0, program_number)
            print(f"FluidSynth: Selected program {program_number} for {source.name}")
            
            # Set gain to match shared instance (gradually to prevent pops)
            target_gain = default_settings.gain
            steps = 10
            for i in range(steps + 1):
                current_gain = (target_gain * i) / steps
                try:
                    fs.setting('synth.gain', current_gain)
                    # Small delay to prevent pops
                    import time
                    time.sleep(0.01)  # 10ms delay between steps
                except Exception as e:
                    print(f"Warning: Could not set FluidSynth gain: {e}")
                    break
            print(f"FluidSynth: Gain set to {target_gain} for {source.name}")
            
            # Create track instance
            instance = TrackAudioInstance(
                track_index=track_index,
                source=source,
                fluidsynth_instance=fs,
                soundfont_id=soundfont_id
            )
            
            self.track_instances[track_index] = instance
            print(f"Soundfont audio initialized for track {track_index}: {source.name}")
            return True
            
        except Exception as e:
            print(f"Error initializing soundfont audio: {e}")
            return False
    
    def _initialize_external_midi(self, track_index: int, source: AudioSource) -> bool:
        """Initialize external MIDI output for a track"""
        if not RTMIDI_AVAILABLE:
            print("rtmidi not available for external MIDI")
            return False
        
        try:
            # Check if we already have this MIDI port open
            if source.midi_port_name in self.midi_out_ports:
                midi_out = self.midi_out_ports[source.midi_port_name]
            else:
                # Create new MIDI output
                midi_out = rtmidi.MidiOut()
                
                # Find the port
                available_ports = midi_out.get_ports()
                port_index = -1
                
                print(f"PerTrackRouter: Looking for MIDI port: '{source.midi_port_name}'")
                print(f"PerTrackRouter: Available ports: {[str(p) for p in available_ports]}")
                
                for i, port_name in enumerate(available_ports):
                    port_name_str = str(port_name)
                    print(f"PerTrackRouter: Checking port {i}: '{port_name_str}' contains '{source.midi_port_name}'?")
                    
                    # Handle encoding issues on macOS for IAC Driver ports
                    if "IAC" in port_name_str and "IAC Driver Bus" in source.midi_port_name:
                        # Extract bus number from corrupted name
                        # 'IAC„Éâ„É©„Ç§„Éê „Éê„Çπ1' -> extract '1'
                        bus_chars = []
                        for char in port_name_str:
                            if char.isdigit():
                                bus_chars.append(char)
                        
                        if bus_chars:
                            detected_bus = ''.join(bus_chars)
                            expected_bus = source.midi_port_name.split()[-1]  # Extract number from "IAC Driver Bus 1"
                            print(f"PerTrackRouter: IAC port detected - bus number: {detected_bus}, expected: {expected_bus}")
                            
                            if detected_bus == expected_bus:
                                port_index = i
                                print(f"PerTrackRouter: Found matching IAC Driver Bus {detected_bus} at index {i}")
                                break
                    elif source.midi_port_name in port_name_str:
                        port_index = i
                        print(f"PerTrackRouter: Found matching port at index {i}")
                        break
                
                if port_index == -1:
                    print(f"MIDI port not found: {source.midi_port_name}")
                    print(f"Available port names: {[str(p) for p in available_ports]}")
                    midi_out.close_port()
                    del midi_out
                    return False
                
                # Open the port
                midi_out.open_port(port_index)
                self.midi_out_ports[source.midi_port_name] = midi_out
            
            # Create track instance
            instance = TrackAudioInstance(
                track_index=track_index,
                source=source,
                midi_out_port=midi_out
            )
            
            self.track_instances[track_index] = instance
            print(f"External MIDI initialized for track {track_index}: {source.name}")
            return True
            
        except Exception as e:
            print(f"Error initializing external MIDI: {e}")
            return False
    
    def _initialize_internal_fluidsynth(self, track_index: int, source: AudioSource) -> bool:
        """Use the existing internal FluidSynth for a track"""
        # Update manager references if needed
        if not self.audio_manager:
            self._update_manager_references()
        
        if not self.audio_manager:
            print("No audio manager available for internal FluidSynth")
            return False
        
        # Extract channel from source name if it's channel-specific
        channel = track_index  # Default to track index as channel
        if source.name.startswith("internal_fluidsynth_ch"):
            try:
                channel = int(source.name.split("ch")[1])
            except (ValueError, IndexError):
                channel = track_index
        
        # Create a new AudioSource with correct channel assignment
        channel_source = AudioSource(
            name=source.name,
            source_type=source.source_type,
            channel=channel,
            program=source.program,
            file_path=source.file_path,
            midi_port_name=source.midi_port_name
        )
        
        # Create track instance that uses the global audio manager
        instance = TrackAudioInstance(
            track_index=track_index,
            source=channel_source
        )
        
        self.track_instances[track_index] = instance
        
        # Set the program for this channel on the FluidSynth instance
        if self.audio_manager and hasattr(self.audio_manager, 'fluidsynth_audio'):
            fluidsynth = self.audio_manager.fluidsynth_audio
            if fluidsynth and hasattr(fluidsynth, 'fs'):
                try:
                    # Set program for this specific channel
                    fluidsynth.fs.program_select(channel, fluidsynth.sfid, 0, channel_source.program)
                    print(f"Set program {channel_source.program} for channel {channel}")
                except Exception as e:
                    print(f"Warning: Could not set program for channel {channel}: {e}")
        
        print(f"Internal FluidSynth assigned to track {track_index}: {source.name} (ch={channel}, prog={channel_source.program})")
        return True
    
    def play_note(self, track_index: int, note: MidiNote) -> bool:
        """Play a note using the track's assigned audio source"""
        instance = self.track_instances.get(track_index)
        if not instance:
            print(f"PerTrackRouter: No instance for track {track_index}, attempting to initialize...")
            # Try to initialize if not done yet
            if not self.initialize_track_audio(track_index):
                print(f"PerTrackRouter: Failed to initialize track {track_index}")
                return False
            instance = self.track_instances.get(track_index)
            if not instance:
                print(f"PerTrackRouter: Still no instance for track {track_index} after initialization")
                return False
        
        try:
            print(f"PerTrackRouter: Playing note {note.pitch} on track {track_index}, source type: {instance.source.source_type}")
            
            if instance.source.source_type == AudioSourceType.SOUNDFONT:
                print(f"PerTrackRouter: Using soundfont audio for track {track_index}")
                return self._play_soundfont_note(instance, note)
            elif instance.source.source_type == AudioSourceType.EXTERNAL_MIDI:
                print(f"PerTrackRouter: Using external MIDI for track {track_index}")
                return self._play_external_midi_note(instance, note)
            
        except Exception as e:
            print(f"Error playing note on track {track_index}: {e}")
            return False
        
        return False
    
    def stop_note(self, track_index: int, note: MidiNote) -> bool:
        """Stop a note using the track's assigned audio source"""
        instance = self.track_instances.get(track_index)
        if not instance:
            return False
        
        try:
            if instance.source.source_type == AudioSourceType.SOUNDFONT:
                return self._stop_soundfont_note(instance, note)
            elif instance.source.source_type == AudioSourceType.EXTERNAL_MIDI:
                return self._stop_external_midi_note(instance, note)
            
        except Exception as e:
            print(f"Error stopping note on track {track_index}: {e}")
            return False
        
        return False
    
    def _play_soundfont_note(self, instance: TrackAudioInstance, note: MidiNote) -> bool:
        """Play note using dedicated FluidSynth instance"""
        if not instance.fluidsynth_instance:
            return False
        
        fs = instance.fluidsynth_instance
        fs.noteon(note.channel, note.pitch, note.velocity)
        return True
    
    def _stop_soundfont_note(self, instance: TrackAudioInstance, note: MidiNote) -> bool:
        """Stop note using dedicated FluidSynth instance"""
        if not instance.fluidsynth_instance:
            return False
        
        fs = instance.fluidsynth_instance
        fs.noteoff(note.channel, note.pitch)
        return True
    
    def _play_external_midi_note(self, instance: TrackAudioInstance, note: MidiNote) -> bool:
        """Play note using external MIDI device via MIDI routing system"""
        print(f"PerTrackRouter: _play_external_midi_note called for pitch {note.pitch}")
        print(f"PerTrackRouter: midi_routing_manager available: {self.midi_routing_manager is not None}")
        print(f"PerTrackRouter: instance.midi_out_port available: {instance.midi_out_port is not None}")
        
        if self.midi_routing_manager:
            print(f"PerTrackRouter: Using MIDI routing system for external MIDI (channel {note.channel}, pitch {note.pitch})")
            # Use MIDI routing system to respect enable_external_routing setting
            self.midi_routing_manager.play_note(note.channel, note.pitch, note.velocity)
            return True
        elif instance.midi_out_port:
            print(f"PerTrackRouter: Using direct MIDI output as fallback")
            # Fallback to direct MIDI output if routing not available
            # Create MIDI note on message
            midi_msg = [0x90 | note.channel, note.pitch, note.velocity]
            instance.midi_out_port.send_message(midi_msg)
            return True
        
        print(f"PerTrackRouter: No MIDI output method available for external MIDI")
        return False
    
    def _stop_external_midi_note(self, instance: TrackAudioInstance, note: MidiNote) -> bool:
        """Stop note using external MIDI device via MIDI routing system"""
        if self.midi_routing_manager:
            # Use MIDI routing system to respect enable_external_routing setting
            self.midi_routing_manager.stop_note(note.channel, note.pitch)
            return True
        elif instance.midi_out_port:
            # Fallback to direct MIDI output if routing not available
            # Create MIDI note off message
            midi_msg = [0x80 | note.channel, note.pitch, 0]
            instance.midi_out_port.send_message(midi_msg)
            return True
        return False
    
    def _play_internal_note(self, instance: TrackAudioInstance, note: MidiNote) -> bool:
        """Play note using internal FluidSynth via MIDI routing system"""
        if self.midi_routing_manager:
            # Use MIDI routing system with the track's channel
            self.midi_routing_manager.play_note(instance.source.channel, note.pitch, note.velocity)
            return True
        elif self.audio_manager:
            # Fallback to direct audio manager with channel information
            success = self.audio_manager.play_note_immediate(note.pitch, note.velocity, instance.source.channel)
            return success
        return False
    
    def _stop_internal_note(self, instance: TrackAudioInstance, note: MidiNote) -> bool:
        """Stop note using internal FluidSynth via MIDI routing system"""
        if self.midi_routing_manager:
            # Use MIDI routing system with the track's channel
            self.midi_routing_manager.stop_note(instance.source.channel, note.pitch)
            return True
        elif self.audio_manager:
            # Fallback to direct audio manager with channel information
            return self.audio_manager.stop_note_immediate(note.pitch, instance.source.channel)
        return False
    
    def cleanup_track_audio(self, track_index: int):
        """Clean up audio resources for a track"""
        instance = self.track_instances.get(track_index)
        if not instance:
            return
        
        try:
            # Clean up FluidSynth instance
            if instance.fluidsynth_instance:
                instance.fluidsynth_instance.delete()
            
            # Note: Don't close MIDI ports here as they might be shared
            # They will be closed in cleanup_all()
            
            del self.track_instances[track_index]
            print(f"Cleaned up audio for track {track_index}")
            
        except Exception as e:
            print(f"Error cleaning up track {track_index} audio: {e}")
    
    def initialize_all_tracks(self, max_tracks: int = 16):
        """Initialize audio for all tracks"""
        success_count = 0
        for track_index in range(max_tracks):
            if self.initialize_track_audio(track_index):
                success_count += 1
        
        print(f"Initialized audio for {success_count}/{max_tracks} tracks")
        return success_count
    
    def cleanup_all(self):
        """Clean up all audio resources"""
        # Clean up all track instances
        for track_index in list(self.track_instances.keys()):
            self.cleanup_track_audio(track_index)
        
        # Close all MIDI output ports
        for port_name, midi_out in self.midi_out_ports.items():
            try:
                midi_out.close_port()
                del midi_out
            except Exception as e:
                print(f"Error closing MIDI port {port_name}: {e}")
        
        self.midi_out_ports.clear()
        print("All per-track audio resources cleaned up")
    
    def stop_all_notes(self):
        """Stop all notes on all track instances"""
        stopped_count = 0
        
        for track_index, instance in self.track_instances.items():
            try:
                if instance.source.source_type == AudioSourceType.SOUNDFONT:
                    # Send all notes off to FluidSynth
                    if instance.fluidsynth_instance:
                        fs = instance.fluidsynth_instance
                        # Send MIDI CC 123 (All Notes Off) on all channels
                        for channel in range(16):
                            try:
                                fs.cc(channel, 123, 0)  # All Notes Off
                                stopped_count += 1
                            except:
                                pass
                        print(f"Sent all-notes-off to track {track_index} soundfont")
                
                elif instance.source.source_type == AudioSourceType.EXTERNAL_MIDI:
                    # Send all notes off to external MIDI
                    if instance.midi_out_port:
                        for channel in range(16):
                            try:
                                # MIDI CC 123 (All Notes Off)
                                midi_msg = [0xB0 | channel, 123, 0]
                                instance.midi_out_port.send_message(midi_msg)
                                stopped_count += 1
                            except:
                                pass
                        print(f"Sent all-notes-off to track {track_index} MIDI device")
                
            except Exception as e:
                print(f"Error stopping notes on track {track_index}: {e}")
        
        print(f"PerTrackAudioRouter: Sent all-notes-off to {stopped_count} channels")
        return stopped_count > 0

# Global per-track audio router instance
_per_track_router: Optional[PerTrackAudioRouter] = None

def get_per_track_audio_router() -> Optional[PerTrackAudioRouter]:
    """Get the global per-track audio router"""
    return _per_track_router

def initialize_per_track_audio_router() -> PerTrackAudioRouter:
    """Initialize the global per-track audio router"""
    global _per_track_router
    _per_track_router = PerTrackAudioRouter()
    return _per_track_router

def cleanup_per_track_audio_router():
    """Clean up the global per-track audio router"""
    global _per_track_router
    if _per_track_router:
        _per_track_router.cleanup_all()
        _per_track_router = None