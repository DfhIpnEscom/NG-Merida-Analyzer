-- Script para crear tabla de ejemplo para SQL Polling
-- Ajusta según la estructura de tu tabla existente

USE Merida_VW;
GO

-- Crear tabla si no existe (ajusta los campos según tu estructura real)
IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[AudioQueue]') AND type in (N'U'))
BEGIN
    CREATE TABLE [dbo].[AudioQueue](
        [TransactionId] [int] IDENTITY(1,1) NOT NULL,
        [RutaAudio] [nvarchar](500) NOT NULL,
        [Estado] [nvarchar](50) NOT NULL DEFAULT 'Pendiente',
        [FechaCreacion] [datetime] NOT NULL DEFAULT GETDATE(),
        [FechaActualizacion] [datetime] NULL,
        CONSTRAINT [PK_AudioQueue] PRIMARY KEY CLUSTERED ([TransactionId] ASC)
    ) ON [PRIMARY]
    
    PRINT 'Tabla AudioQueue creada exitosamente'
END
ELSE
BEGIN
    PRINT 'La tabla AudioQueue ya existe'
END
GO

-- Crear índice para mejorar performance de consultas
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_AudioQueue_Estado' AND object_id = OBJECT_ID('AudioQueue'))
BEGIN
    CREATE NONCLUSTERED INDEX [IX_AudioQueue_Estado]
    ON [dbo].[AudioQueue] ([Estado])
    INCLUDE ([TransactionId], [RutaAudio])
    
    PRINT 'Índice IX_AudioQueue_Estado creado exitosamente'
END
GO

-- Ejemplo de inserción de registros de prueba
-- Ajusta las rutas según tu estructura de archivos
/*
INSERT INTO AudioQueue (RutaAudio, Estado)
VALUES 
    ('D:\Audio\llamada001.wav', 'Pendiente'),
    ('D:\Audio\llamada002.wav', 'Pendiente'),
    ('D:\Audio\llamada003.wav', 'Pendiente');
*/

-- Consulta para ver los registros pendientes
SELECT TOP 10 
    TransactionId,
    RutaAudio,
    Estado,
    FechaCreacion
FROM AudioQueue
WHERE Estado = 'Pendiente'
ORDER BY TransactionId;
GO