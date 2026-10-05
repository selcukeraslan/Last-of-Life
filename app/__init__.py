# Sistem sertifika deposunu kullan (macOS'ta python.org kurulumu ve kurumsal/antivirüs proxy'leri için)
try:
    import truststore

    truststore.inject_into_ssl()
except ImportError:
    pass
