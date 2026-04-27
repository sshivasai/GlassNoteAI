use anyhow::Result;
use base64::Engine;
use tracing::debug;

#[cfg(target_os = "windows")]
pub async fn capture_fullscreen() -> Result<String> {
    tokio::task::spawn_blocking(|| capture_fullscreen_windows()).await?
}

#[cfg(target_os = "macos")]
pub async fn capture_fullscreen() -> Result<String> {
    tokio::task::spawn_blocking(|| capture_fullscreen_macos()).await?
}

#[cfg(target_os = "windows")]
fn capture_fullscreen_windows() -> Result<String> {
    use windows::Win32::Graphics::Gdi::*;
    use windows::Win32::UI::WindowsAndMessaging::*;

    let start = std::time::Instant::now();

    unsafe {
        let hdc_screen = GetDC(None);
        let width = GetSystemMetrics(SM_CXSCREEN);
        let height = GetSystemMetrics(SM_CYSCREEN);

        let hdc_mem = CreateCompatibleDC(hdc_screen);
        let hbitmap = CreateCompatibleBitmap(hdc_screen, width, height);
        SelectObject(hdc_mem, hbitmap);

        BitBlt(hdc_mem, 0, 0, width, height, hdc_screen, 0, 0, SRCCOPY);

        // Convert HBITMAP to image
        let mut bmp_info = BITMAPINFO {
            bmiHeader: BITMAPINFOHEADER {
                biSize: std::mem::size_of::<BITMAPINFOHEADER>() as u32,
                biWidth: width,
                biHeight: -height, // Top-down bitmap
                biPlanes: 1,
                biBitCount: 32,
                biCompression: BI_RGB.0,
                ..Default::default()
            },
            ..Default::default()
        };

        let mut buffer = vec![0u8; (width * height * 4) as usize];
        GetDIBits(
            hdc_mem,
            hbitmap,
            0,
            height as u32,
            Some(buffer.as_mut_ptr() as *mut _),
            &mut bmp_info,
            DIB_RGB_COLORS,
        );

        DeleteObject(hbitmap);
        DeleteDC(hdc_mem);
        ReleaseDC(None, hdc_screen);

        // Convert BGRA to RGBA
        for chunk in buffer.chunks_exact_mut(4) {
            chunk.swap(0, 2); // B <-> R
        }

        // Encode as PNG
        let mut png_data = Vec::new();
        {
            let mut encoder = image::codecs::png::PngEncoder::new(&mut png_data);
            encoder
                .encode(&buffer, width as u32, height as u32, image::ColorType::Rgba8)
                .expect("PNG encoding failed");
        }

        // Base64 encode
        let base64_string = base64::engine::general_purpose::STANDARD.encode(&png_data);

        let elapsed = start.elapsed();
        debug!("Windows screenshot captured in {:?}", elapsed);

        Ok(base64_string)
    }
}

#[cfg(target_os = "macos")]
fn capture_fullscreen_macos() -> Result<String> {
    use core_graphics::display::{CGDisplay, CGDisplayStreamUpdateRef, CGImage};
    use core_graphics::image::CGImageRef;
    use image::{ImageBuffer, Rgba};

    let start = std::time::Instant::now();

    // Get main display
    let display = CGDisplay::main();
    let image: CGImage = display.image()?;

    // Get image dimensions
    let width = image.width();
    let height = image.height();
    let bytes_per_row = image.bytes_per_row();

    // Get raw image data
    let data = image.data();
    let data_provider = data.bytes();

    // Convert to RGBA image
    let mut img_buffer: ImageBuffer<Rgba<u8>, Vec<u8>> = ImageBuffer::new(width as u32, height as u32);

    for y in 0..height {
        for x in 0..width {
            let offset = y * bytes_per_row + x * 4;

            if offset + 3 < data_provider.len() {
                let b = data_provider[offset];
                let g = data_provider[offset + 1];
                let r = data_provider[offset + 2];
                let a = data_provider[offset + 3];

                img_buffer.put_pixel(x as u32, y as u32, Rgba([r, g, b, a]));
            }
        }
    }

    // Encode as PNG
    let mut png_data = Vec::new();
    {
        let mut encoder = image::codecs::png::PngEncoder::new(&mut png_data);
        encoder
            .encode(
                img_buffer.as_raw(),
                width as u32,
                height as u32,
                image::ColorType::Rgba8,
            )
            .expect("PNG encoding failed");
    }

    // Base64 encode
    let base64_string = base64::engine::general_purpose::STANDARD.encode(&png_data);

    let elapsed = start.elapsed();
    debug!("macOS screenshot captured in {:?}", elapsed);

    Ok(base64_string)
}

#[cfg(not(any(target_os = "windows", target_os = "macos")))]
pub async fn capture_fullscreen() -> Result<String> {
    anyhow::bail!("Screen capture only supported on Windows and macOS")
}
